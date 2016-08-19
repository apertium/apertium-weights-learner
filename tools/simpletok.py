#! /usr/bin/python3

import sys, re

beforepunc_re = re.compile(r'([¿("/])(\w)')
afterpunc_re = re.compile(r'(\w)([;:,.!?)"/—])')
quot_re = re.compile("[«»`'“”„‘’‛]")
numfix_re = re.compile('([0-9]) ([,.:][0-9])')
beforedash_re = re.compile(r'(\W)-(\w)')
afterdash_re = re.compile(r'(\w)-(\W)')

def normalize(line):
    line = line.lower().replace('--', '—').replace(' - ', ' — ')
    line = quot_re.sub('"', line)
    line = beforedash_re.sub(r'\1— \2', afterdash_re.sub(r'\1 —\2', line))
    line = beforepunc_re.sub(r'\1 \2', afterpunc_re.sub(r'\1 \2', line))
    line = numfix_re.sub(r'\1\2', line)
    return line

if __name__ == "__main__":
    with open(sys.argv[1], 'r', encoding='utf-8') as ifile,\
         open(sys.argv[2], 'w', encoding='utf-8') as ofile:
        for line in ifile:
            ofile.write(normalize(line))
