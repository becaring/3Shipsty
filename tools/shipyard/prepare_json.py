"""Generate hash-locked nlohmann 3.12.0 lexer/Grisu2 for the bounded XDK backend.

Original basic_json and ordered_json are not lowered. No application source changes.
"""
from pathlib import Path
import hashlib,json,runpy
ROOT=Path(__file__).resolve().parents[2]
BACKEND=ROOT/'platform/shipyard/json'
SOURCE=BACKEND/'upstream'
OUT=ROOT/'scratch/json-xdk/backend-generated/json/generated'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def generate(source=SOURCE,output=OUT):
    source,output=Path(source).resolve(),Path(output).resolve()
    if not output.is_relative_to((ROOT/'scratch/json-xdk').resolve()):
        raise ValueError('output must remain in owned scratch/json-xdk')
    lock=json.loads((BACKEND/'source-authority.json').read_text())
    for rel,digest in lock['upstream_files'].items():
        if sha((source/rel).read_bytes())!=digest:raise ValueError('upstream source SHA-256 mismatch: '+rel)
    for rel,record in lock['donor_files'].items():
        if sha((BACKEND/rel).read_bytes())!=record['owned_sha256']:raise ValueError('backend source SHA-256 mismatch: '+rel)
    for rel,digest in lock.get('owned_additions',{}).items():
        if sha((BACKEND/rel).read_bytes())!=digest:raise ValueError('backend addition SHA-256 mismatch: '+rel)
    algorithms=runpy.run_path(str(BACKEND/'generate_algorithms.py'))['generate'](source,output)
    streams=runpy.run_path(str(BACKEND/'generate_streams.py'))['generate'](source,output)
    ordered=runpy.run_path(str(BACKEND/'generate_ordered.py'))['generate'](source,output)
    ordered_consumers=runpy.run_path(str(BACKEND/'generate_ordered_consumers.py'))['generate'](output)
    containers=runpy.run_path(str(BACKEND/'generate_containers.py'))['generate'](output)
    manifest={'official_commit':lock['official_commit'],'backend_kind':'bounded API, not generic basic_json','full_modern_soh_json_contract':False,'upstream_inputs':lock['upstream_files'],'backend_inputs':{r:v['owned_sha256'] for r,v in lock['donor_files'].items()},'owned_additions':lock.get('owned_additions',{}),'generator_sha256':sha(Path(__file__).read_bytes()),'algorithms':algorithms,'streams':streams,'ordered':ordered,'ordered_consumers':ordered_consumers,'containers':containers}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest
if __name__=='__main__':
    generate(); print('Generated pinned nlohmann 3.12.0 lexer/Grisu2; modern application API gaps remain explicit')
