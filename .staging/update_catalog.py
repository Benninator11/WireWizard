import base64, collections, io, json, re, zipfile
from pathlib import Path
root = Path(".")
parts = sorted((root / ".staging" / "archive.parts").glob("*.b64"))
if not parts: raise RuntimeError("Archivteile fehlen")
archive_bytes = base64.b64decode("".join(p.read_text(encoding="ascii").strip() for p in parts))
with zipfile.ZipFile(io.BytesIO(archive_bytes)) as z:
    cpu_raw = z.read("Beide-Listen/cpus_all.txt")
    gpu_raw = z.read("Beide-Listen/gpus_all.txt")
def parse(raw, name):
    rows = []
    for number, line in enumerate(raw.decode("utf-8-sig").splitlines(), 1):
        if not line.strip(): continue
        row = [v.strip() for v in line.split("|")]
        if len(row) != 7: raise ValueError(f"{name}:{number}: 7 Felder erwartet, {len(row)} erhalten")
        rows.append(row)
    return rows
cpus, gpus = parse(cpu_raw, "CPU"), parse(gpu_raw, "GPU")
if len(cpus) != 8370 or len(gpus) != 2670:
    raise ValueError(f"Unerwartete Eintragszahl: CPU {len(cpus)}, GPU {len(gpus)}")
(root / "CPU-List.txt").write_bytes(cpu_raw)
(root / "GPU-List.txt").write_bytes(gpu_raw)
def labels(rows):
    bases = []
    for row in rows:
        vendor, model = row[1], row[4]
        bases.append(model if model.lower().startswith(vendor.lower() + " ") else vendor + " " + model)
    counts = collections.Counter(bases)
    result, used = [], set()
    for row, base in zip(rows, bases):
        year, vendor, arch, family, model, device_type, details = row
        label = base
        if counts[base] > 1: label += f" — {vendor} · {family} · {year} · {device_type}"
        if label in used: label += f" · {arch}"
        if label in used: label += f" · {details}"
        if label in used:
            i, candidate = 2, label
            while candidate in used:
                candidate = f"{label} #{i}"
                i += 1
            label = candidate
        used.add(label)
        result.append(label)
    return result
cpu_labels, gpu_labels = labels(cpus), labels(gpus)
def memory_type(value):
    match = re.search(r"\b(HBM\d*[A-Za-z]*|GDDR\d*[A-Za-z]*|LPDDR\d*[A-Za-z]*|DDR\d*[A-Za-z]*|SDRAM|SGRAM)\b", value, re.I)
    return match.group(1).upper() if match else ""
cpu_rows = []
for row, label in zip(cpus, cpu_labels):
    year, vendor, architecture, family, model, device_type, core_threads = row
    match = re.match(r"^\s*(\d+(?:\s*\+\s*\d+)?)\s*/\s*(\d+)", core_threads)
    cores = match.group(1).replace(" ", "") if match else core_threads
    threads = match.group(2) if match else ""
    cpu_rows.append([label, cores, threads, "—", "—", year, architecture, "", "Beide-Listen.zip / cpus_all.txt", "", "", "", "", vendor, family, device_type, model])
gpu_rows = []
for row, label in zip(gpus, gpu_labels):
    year, vendor, architecture, chipset, model, device_type, vram = row
    gpu_rows.append([label, vram or "Nicht ermittelt", "", year, "Basisdaten aus gpus_all.txt; TDP- und Taktwerte sind dort nicht enthalten.", "", "", "", memory_type(vram), architecture, "", "Beide-Listen.zip / gpus_all.txt", f"Hersteller: {vendor}; Chipsatz/Familie: {chipset}; Gerätetyp: {device_type}", vendor, chipset, device_type, model])
path = root / "index.html"
html = path.read_text(encoding="utf-8")
marker = 'id="cable-html-source"'
start = html.find(marker)
if start < 0: raise RuntimeError("WireWizard-Abschnitt nicht gefunden")
def bounds(text, declaration, offset):
    p = text.find(declaration, offset)
    if p < 0: raise RuntimeError("Deklaration fehlt: " + declaration)
    a = text.find("[", p)
    depth, quote, escaped = 0, None, False
    for i in range(a, len(text)):
        c = text[i]
        if quote:
            if escaped: escaped = False
            elif c == "\\": escaped = True
            elif c == quote: quote = None
        else:
            if c in ("'", '"', chr(96)): quote = c
            elif c == "[": depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0: return a, i + 1
    raise RuntimeError("Array-Ende fehlt: " + declaration)
def replace_array(text, declaration, offset, values):
    a, b = bounds(text, declaration, offset)
    return text[:a] + json.dumps(values, ensure_ascii=False, separators=(",", ":")) + text[b:]
def append_array(text, declaration, offset, values):
    a, b = bounds(text, declaration, offset)
    existing = json.loads(text[a:b])
    return text[:a] + json.dumps(existing + values, ensure_ascii=False, separators=(",", ":")) + text[b:]
html = replace_array(html, "const cpuNames = [", start, cpu_labels)
html = replace_array(html, "const gpuNames = [", start, gpu_labels)
start = html.find(marker)
html = append_array(html, "const plannerCpuHardwareRows = [", start, cpu_rows)
html = append_array(html, "const plannerGpuHardwareRows = [", start, gpu_rows)
start = html.find(marker)
tail = html[start:]
old = """          socket: row[9], process: row[10], graphics: row[11], memory: row[12]
"""
new = """          socket: row[9], process: row[10], graphics: row[11], memory: row[12],
          vendor: row[13] || '', family: row[14] || '', deviceType: row[15] || '', catalogModel: row[16] || row[0]
"""
if old not in tail: raise RuntimeError("CPU-Mapping nicht gefunden")
tail = tail.replace(old, new, 1)
old = """          memoryType: row[8], architecture: row[9], memoryBandwidth: row[10], source: row[11], specialNotes: row[12]
"""
new = """          memoryType: row[8], architecture: row[9], memoryBandwidth: row[10], source: row[11], specialNotes: row[12],
          vendor: row[13] || '', chipset: row[14] || '', deviceType: row[15] || '', catalogModel: row[16] || row[0]
"""
if old not in tail: raise RuntimeError("GPU-Mapping nicht gefunden")
tail = tail.replace(old, new, 1)
start_fn = tail.find("      function addPlannerHardwareRow(exactMap, normalizedMap, name, spec) {")
if start_fn < 0: raise RuntimeError("Hardware-Merge-Funktion nicht gefunden")
end_fn = tail.find("\n      }\n", start_fn) + len("\n      }\n")
if end_fn <= start_fn: raise RuntimeError("Ende der Merge-Funktion fehlt")
new_fn = """      function addPlannerHardwareRow(exactMap, normalizedMap, name, spec) {
        const exact = String(name || '').trim().toLocaleLowerCase();
        if (!exact) return;
        const missing = (value) => {
          const text = String(value ?? '').trim();
          return !text || /^(?:—|-|n\\/a|nicht ermittelt|nicht verifiziert|not verified|unknown|unbekannt)$/i.test(text);
        };
        const merge = (oldValue, incoming) => {
          if (!oldValue) return incoming;
          const result = { ...oldValue };
          Object.keys(incoming).forEach((key) => {
            if (missing(result[key]) && !missing(incoming[key])) result[key] = incoming[key];
          });
          return result;
        };
        exactMap[exact] = Object.prototype.hasOwnProperty.call(exactMap, exact) ? merge(exactMap[exact], spec) : spec;
        const normalized = normalizePlannerHardwareName(name);
        if (!normalized) return;
        if (!Object.prototype.hasOwnProperty.call(normalizedMap, normalized)) normalizedMap[normalized] = spec;
        else if (normalizedMap[normalized] && normalizedMap[normalized].name !== spec.name) normalizedMap[normalized] = null;
      }
"""
tail = tail[:start_fn] + new_fn + tail[end_fn:]
old = """            socket: cpu.socket, process: cpu.process, graphics: cpu.graphics, memory: cpu.memory, source: cpu.source
"""
new = """            socket: cpu.socket, process: cpu.process, graphics: cpu.graphics, memory: cpu.memory, source: cpu.source,
            vendor: cpu.vendor, family: cpu.family, deviceType: cpu.deviceType, catalogModel: cpu.catalogModel
"""
if old not in tail: raise RuntimeError("CPU-Speicherzuordnung nicht gefunden")
tail = tail.replace(old, new, 1)
old = """            source: gpu.source, specialNotes: gpu.specialNotes
"""
new = """            source: gpu.source, specialNotes: gpu.specialNotes, vendor: gpu.vendor,
            chipset: gpu.chipset, deviceType: gpu.deviceType, catalogModel: gpu.catalogModel
"""
if old not in tail: raise RuntimeError("GPU-Speicherzuordnung nicht gefunden")
tail = tail.replace(old, new, 1)
old = """      function isMobileCpuName(name) {
        return /mobile|laptop|notebook|snapdragon|apple\\s+[am]\\d|mediatek|dimensity|exynos|arm cortex|celeron n\\d|pentium silver n|atom x[357]|ryzen z\\d|ryzen ai/i.test(name)
"""
new = """      function isMobileCpuName(name) {
        const catalog = getPlannerCpuHardwareSpec(name);
        if (catalog?.deviceType && /notebook|mobile|laptop/i.test(catalog.deviceType)) return true;
        return /mobile|laptop|notebook|snapdragon|apple\\s+[am]\\d|mediatek|dimensity|exynos|arm cortex|celeron n\\d|pentium silver n|atom x[357]|ryzen z\\d|ryzen ai/i.test(name)
"""
if old not in tail: raise RuntimeError("CPU-Gerätetypfilter nicht gefunden")
tail = tail.replace(old, new, 1)
old = """      function isMobileGpuName(name) {
        // UHD 730/750/770 gibt es nur am Desktop
"""
new = """      function isMobileGpuName(name) {
        const catalog = getPlannerGpuHardwareSpec(name);
        if (catalog?.deviceType) return /notebook|mobile|laptop/i.test(catalog.deviceType);
        // UHD 730/750/770 gibt es nur am Desktop
"""
if old not in tail: raise RuntimeError("GPU-Gerätetypfilter nicht gefunden")
tail = tail.replace(old, new, 1)
metadata = """
      function createHardwareDataNote(input, id) {
        const note = document.createElement('div');
        note.id = id;
        note.hidden = true;
        note.setAttribute('role', 'status');
        note.style.cssText = 'margin-top:7px;padding:8px 10px;border:1px solid var(--border);border-radius:8px;background:var(--panel-soft);color:var(--muted);font-size:11px;line-height:1.5;overflow-wrap:anywhere;';
        input.closest('.field').appendChild(note);
        return note;
      }
      const cpuHardwareDataNote = createHardwareDataNote(ui.cpuModel, 'cpuHardwareDataNote');
      const gpuHardwareDataNote = createHardwareDataNote(ui.gpuModel, 'gpuHardwareDataNote');
      function updateWireHardwareMetadata() {
        const en = state.lang === 'en';
        const cpu = getPlannerCpuHardwareSpec(ui.cpuModel.value);
        const gpu = getPlannerGpuHardwareSpec(ui.gpuModel.value);
        if (cpu) {
          const parts = [];
          if (cpu.vendor) parts.push((en ? 'Manufacturer: ' : 'Hersteller: ') + cpu.vendor);
          if (cpu.family) parts.push((en ? 'Family: ' : 'Familie: ') + cpu.family);
          if (cpu.year && !/nicht ermittelt|nicht verifiziert/i.test(cpu.year)) parts.push((en ? 'Year: ' : 'Jahr: ') + cpu.year);
          if (cpu.architecture) parts.push((en ? 'Architecture: ' : 'Architektur: ') + cpu.architecture);
          const cores = plannerCoreCount(cpu), threads = plannerNumberFromSpec(cpu.threads);
          if (cores) parts.push(cores + (en ? ' cores' : ' Kerne'));
          if (threads) parts.push(threads + (en ? ' threads' : ' Threads'));
          if (cpu.deviceType) parts.push((en ? 'Type: ' : 'Typ: ') + cpu.deviceType);
          cpuHardwareDataNote.textContent = parts.join(' · ');
          cpuHardwareDataNote.hidden = !parts.length;
        } else { cpuHardwareDataNote.textContent = ''; cpuHardwareDataNote.hidden = true; }
        if (gpu) {
          const parts = [];
          if (gpu.vendor) parts.push((en ? 'Manufacturer: ' : 'Hersteller: ') + gpu.vendor);
          if (gpu.chipset) parts.push((en ? 'Family/chipset: ' : 'Familie/Chipsatz: ') + gpu.chipset);
          if (gpu.yearInfo && !/nicht ermittelt|nicht verifiziert/i.test(gpu.yearInfo)) parts.push((en ? 'Year: ' : 'Jahr: ') + gpu.yearInfo);
          if (gpu.architecture) parts.push((en ? 'Architecture: ' : 'Architektur: ') + gpu.architecture);
          if (gpu.vramInfo) parts.push('VRAM: ' + gpu.vramInfo);
          if (gpu.deviceType) parts.push((en ? 'Type: ' : 'Typ: ') + gpu.deviceType);
          gpuHardwareDataNote.textContent = parts.join(' · ');
          gpuHardwareDataNote.hidden = !parts.length;
        } else { gpuHardwareDataNote.textContent = ''; gpuHardwareDataNote.hidden = true; }
      }
      ui.cpuModel.addEventListener('input', updateWireHardwareMetadata);
      ui.cpuModel.addEventListener('change', updateWireHardwareMetadata);
      ui.gpuModel.addEventListener('input', updateWireHardwareMetadata);
      ui.gpuModel.addEventListener('change', updateWireHardwareMetadata);
      const openDeviceModalWithHardwareMetadata = openDeviceModal;
      openDeviceModal = function (...args) {
        openDeviceModalWithHardwareMetadata(...args);
        updateWireHardwareMetadata();
      };
"""
anchor = "      // Zum Start die Controls verbinden und einmal rendern."
if anchor not in tail: raise RuntimeError("Initialisierungsanker fehlt")
tail = tail.replace(anchor, metadata + "\n" + anchor, 1)
old = "        populateHardwareLists();\n      render();"
new = "        populateHardwareLists();\n        updateWireHardwareMetadata();\n      render();"
if old not in tail: raise RuntimeError("Initialisierung nicht gefunden")
tail = tail.replace(old, new, 1)
html = html[:start] + tail
path.write_text(html, encoding="utf-8")
readme_path = root / "README.md"
readme = readme_path.read_text(encoding="utf-8")
section = """## CPU- und GPU-Datenbank

WireWizard verwendet die vollständigen Modelllisten aus CPU-List.txt und GPU-List.txt:

- **8.370 CPU-Datensätze** mit Modell, Hersteller, Jahr, Architektur, Familie, Gerätetyp sowie Kern-/Thread-Angabe.
- **2.670 GPU-Datensätze** mit Modell, Hersteller, Jahr, Architektur, Chipsatz/Familie, Gerätetyp und VRAM-/Speichertyp.

Die Modell-Auswahl verwendet diese Listen. Bei der Auswahl zeigt das Geräteformular die verfügbaren Basisdaten an und speichert sie am Gerät. Vorhandene detailliertere Spezifikationen bleiben erhalten. Takt- und TDP-Werte werden nicht geschätzt, da sie in den gelieferten Listen nicht enthalten sind.

"""
if "## CPU- und GPU-Datenbank" not in readme:
    lines = readme.splitlines()
    readme = lines[0] + "\n\n" + section + "\n".join(lines[1:]) + "\n"
    readme_path.write_text(readme, encoding="utf-8")
print(f"OK: {len(cpus)} CPUs und {len(gpus)} GPUs übernommen; Labels eindeutig.")
