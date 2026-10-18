#!/usr/bin/env python3
"""Copy a mounted volume to a new local directory and hash both copies.

Never writes to source. Reports all inaccessible files and source changes.
Not a raw flash, bootloader, or hidden-region backup.
"""
import argparse, datetime, hashlib, json, os, pathlib, stat, time

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def main():
    p = argparse.ArgumentParser()
    p.add_argument('source', type=pathlib.Path)
    p.add_argument('destination', type=pathlib.Path)
    a = p.parse_args()
    src, dst = a.source.resolve(), a.destination.resolve()
    if not src.is_dir() or dst.exists() or src == dst or src in dst.parents:
        p.error('source must exist and destination must be new and outside source')
    dst.mkdir(parents=True)
    rows, errors, directories = [], [], []
    report_path = dst.parent / (dst.name + '-manifest.json')
    def save_report(complete=False):
        report = dict(source=str(src), backup=str(dst),
                      updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      complete=complete,
                      verification_method='source SHA-256 during copy; independent target SHA-256',
                      files=rows, directories=directories, errors=errors,
                      verified=complete and not errors,
                      total_bytes=sum(r['size'] for r in rows))
        if complete:
            report['completed_utc'] = report['updated_utc']
        pending = report_path.with_suffix('.json.tmp')
        with pending.open('w') as f:
            json.dump(report, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        pending.replace(report_path)
        return report
    save_report()
    def onerror(e):
        errors.append(str(e))
    def small_files_first():
        deferred = []
        for root, dirs, files in os.walk(src, onerror=onerror, followlinks=False):
            small = []
            for name in files:
                try:
                    large = (pathlib.Path(root) / name).stat().st_size >= 64 * 1024 * 1024
                except OSError:
                    large = False  # Normal copy handler will record the error.
                if large:
                    deferred.append((root, [], [name]))
                else:
                    small.append(name)
            yield root, dirs, small
        yield from deferred
    for root, dirs, files in small_files_first():
        relroot = pathlib.Path(root).relative_to(src)
        (dst / relroot).mkdir(exist_ok=True)
        if str(relroot) not in directories:
            directories.append(str(relroot))
        for name in sorted(files):
            source = pathlib.Path(root) / name
            rel = source.relative_to(src)
            target = dst / rel
            try:
                before = source.stat()
                if not stat.S_ISREG(before.st_mode) or source.is_symlink():
                    raise ValueError('unsupported nonregular file: ' + str(rel))
                # Hash the exact bytes read from source while copying, then
                # independently reread the local target. Avoid a second slow
                # full-device pass; never read past the known source length.
                h = hashlib.sha256()
                remaining = before.st_size
                last_progress = time.monotonic()
                with source.open('rb') as inp, target.open('xb') as out:
                    while remaining:
                        block = inp.read(min(1024 * 1024, remaining))
                        if not block:
                            raise IOError('unexpected source EOF')
                        h.update(block)
                        out.write(block)
                        remaining -= len(block)
                        if time.monotonic() - last_progress >= 30:
                            print('%s: copied and source-hashed %d / %d bytes' %
                                  (rel, before.st_size - remaining, before.st_size), flush=True)
                            last_progress = time.monotonic()
                    out.flush()
                    os.fsync(out.fileno())
                source_hash, target_hash = h.hexdigest(), digest(target)
                after = source.stat()
                ok = (source_hash == target_hash and before.st_size == after.st_size
                      and before.st_mtime_ns == after.st_mtime_ns)
                rows.append(dict(path=str(rel), size=after.st_size,
                                 mtime_ns=after.st_mtime_ns,
                                 source_sha256=source_hash, backup_sha256=target_hash,
                                 verified=ok))
                if not ok:
                    errors.append('hash mismatch or source changed: ' + str(rel))
                print(str(rel) + ': ' + ('verified' if ok else 'FAILED'), flush=True)
            except Exception as e:
                errors.append(str(rel) + ': ' + str(e))
            save_report()
    original_paths = {r['path'] for r in rows}
    final_paths = set()
    for root, dirs, files in os.walk(src, onerror=onerror):
        final_paths.update(str((pathlib.Path(root)/n).relative_to(src)) for n in files)
    if final_paths != original_paths:
        errors.append('source inventory changed or files could not be copied: ' +
                      repr(sorted(final_paths.symmetric_difference(original_paths))))
    report = save_report(complete=True)
    print(json.dumps({k:v for k,v in report.items() if k not in ('files','directories')}, indent=2))
    raise SystemExit(0 if report['verified'] else 1)

if __name__ == '__main__':
    main()
