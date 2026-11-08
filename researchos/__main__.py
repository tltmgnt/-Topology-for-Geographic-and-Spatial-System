"""Offline ResearchOS/TECT CLI; never executes arbitrary scenario commands."""
import argparse
import json
from .core import canonical
from .io import load, write_bundle, verify_bundle
from .pilot import scenario
from .experiments import evaluate


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    p=commands.add_parser('pilot'); p.add_argument('--output',required=True)
    p=commands.add_parser('evaluate'); p.add_argument('input'); p.add_argument('--output',required=True)
    p=commands.add_parser('verify'); p.add_argument('bundle')
    p=commands.add_parser('benchmark'); p.add_argument('input')
    args=parser.parse_args(argv)
    try:
        if args.command=='verify':
            report=verify_bundle(args.bundle); result={'replay_consistent':True,'report':report}
        elif args.command=='benchmark': result=evaluate(load(args.input))
        else:
            result=write_bundle(scenario() if args.command=='pilot' else load(args.input),args.output)
        print(canonical(result),end='')
        if args.command in ('pilot','evaluate'):
            # A completed bundle can intentionally contain unresolved/failed gates.
            return 0 if all(c['state']=='ASSURED' for c in result['state']['claims'].values()) and result['state']['claims'] else 1
        return 0
    except (ValueError,TypeError,KeyError,OSError,OverflowError,RecursionError) as exc:
        parser.error(str(exc))


if __name__=='__main__': raise SystemExit(main())
