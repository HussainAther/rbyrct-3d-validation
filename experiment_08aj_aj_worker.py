"""Engineering-only real MART worker with post-commit fault-injection hold.

The delay is strictly outside numerical updates and after each committed checkpoint.
Never run against prospective objects; input validation is delegated to AH/AF/AA.
"""
import argparse,json,time
from pathlib import Path
import experiment_08aj_ah as ah


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('worker-dir','af-dir','aa-dir','m-dir'):
        ap.add_argument('--'+name,required=True,type=Path)
    ap.add_argument('--max-mib',type=int,default=8192)
    ap.add_argument('--post-commit-hold',type=float,default=0.4)
    args=ap.parse_args()
    if not (0.05<=args.post_commit_hold<=2):ap.error('invalid post-commit hold')
    # Install OS cap before any numerical arrays can be allocated.
    handle=ah.enforce_memory_cap(args.max_mib)
    original=ah.commit
    def commit_then_hold(*a,**kw):
        result=original(*a,**kw)
        time.sleep(args.post_commit_hold)
        return result
    ah.commit=commit_then_hold
    result=ah.worker_run(args.worker_dir,args.af_dir,args.aa_dir,args.m_dir)
    print(json.dumps(result))

if __name__=='__main__': main()
