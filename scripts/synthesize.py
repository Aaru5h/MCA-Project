#!/usr/bin/env python3
"""Synthesize Deepak's cache RTL to generic Yosys cells (no device timing)."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def yosys_path(path):
    """Quote a path for a Yosys script, without involving a shell."""
    value = str(path)
    if any(char in value for char in '\n\r"\\'):
        raise ValueError('Yosys output paths cannot contain newlines, quotes or backslashes')
    return f'"{value}"'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache-size', type=int, default=1024)
    parser.add_argument('--block-size', type=int, default=16)
    parser.add_argument('--write-allocate', type=int, choices=(0, 1), default=0)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--yosys', default='yosys')
    args = parser.parse_args()
    if (args.block_size < 4 or args.cache_size < args.block_size or
            args.cache_size & (args.cache_size - 1) or
            args.block_size & (args.block_size - 1) or args.cache_size > 2**30):
        parser.error('Require power-of-two sizes: 4 <= block size <= cache size <= 2**30')
    executable = shutil.which(args.yosys)
    if not executable:
        parser.error('Yosys was not found; install it or pass --yosys /path/to/yosys')
    output = (args.output or ROOT / 'docs/synthesis/generated' /
              f'cache{args.cache_size}_block{args.block_size}_wa{args.write_allocate}').resolve()
    try:
        # Validate before creating files.
        yosys_path(output)
    except ValueError as error:
        parser.error(str(error))
    output.mkdir(parents=True, exist_ok=True)
    # A failed rerun must not retain a successful manifest from an earlier run.
    manifest = output / 'run.json'
    manifest.unlink(missing_ok=True)
    script = '\n'.join([
        'read_verilog -sv "rtl/dm_cache.v"',
        f'chparam -set CACHE_SIZE {args.cache_size} -set BLOCK_SIZE {args.block_size} '
        f'-set WRITE_ALLOCATE {args.write_allocate} dm_cache',
        'hierarchy -check -top dm_cache',
        'synth -top dm_cache',
        'check -assert -nolatches',
        f'tee -o {yosys_path(output / "statistics.json")} stat -json',
        f'write_json {yosys_path(output / "netlist.json")}',
        f'write_verilog -noattr {yosys_path(output / "netlist.v")}',
        '',
    ])
    script_path = output / 'synthesis.ys'
    script_path.write_text(script)
    version = subprocess.run([executable, '-V'], capture_output=True, text=True, check=True).stdout.strip()
    command = [executable, '-T', '-s', str(script_path)]
    with (output / 'synthesis.txt').open('w') as log:
        result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    log_text = (output / 'synthesis.txt').read_text()
    warnings = list(dict.fromkeys(line.strip() for line in log_text.splitlines()
                                 if line.lstrip().startswith('Warning:')))
    (output / 'warnings.txt').write_text('\n'.join(warnings) + ('\n' if warnings else ''))
    if result.returncode:
        print(f'Synthesis failed; inspect {output / "synthesis.txt"}', file=sys.stderr)
        return result.returncode
    statistics = json.loads((output / 'statistics.json').read_text())
    if '\\dm_cache' not in statistics['modules']:
        raise RuntimeError('Synthesis statistics do not contain dm_cache')
    metadata = {
        'tool': version,
        'target': 'generic Yosys cells; no FPGA device, ASIC library or clock constraint',
        'top': 'dm_cache',
        'parameters': {'CACHE_SIZE': args.cache_size, 'BLOCK_SIZE': args.block_size,
                       'WRITE_ALLOCATE': args.write_allocate},
        'sources': {'rtl/dm_cache.v': hashlib.sha256((ROOT / 'rtl/dm_cache.v').read_bytes()).hexdigest()},
        'command': command,
        'working_directory': 'repository root',
        'checks': 'check -assert -nolatches passed',
        'warnings': warnings,
        'memory_model': 'main_mem is a simulation model and is not synthesized',
    }
    manifest.write_text(json.dumps(metadata, indent=2) + '\n')
    print(f'Synthesis passed: {output}')
    print(f'Warnings: {len(warnings)}; generic cell statistics: {output / "statistics.json"}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
