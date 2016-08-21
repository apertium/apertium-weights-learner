#! /usr/bin/python3

import sys, re

# regexes used to normalize lines
# for scoring them against language model
# or for sending them to language model training
beforepunc_re = re.compile(r'([¿("/])(\w)')
afterpunc_re = re.compile(r'(\w)([;:,.!?)"/—])')
quot_re = re.compile("[«»`'“”„‘’‛]|&quot;")
numfix_re = re.compile('([0-9]) ([,.:][0-9])')
beforedash_re = re.compile(r'(\W)-(\w)')
afterdash_re = re.compile(r'(\w)-(\W)')

def normalize(line):
    """
    Tokenize and graphically normalize line
    for scoring it against language model
    or for sending it to language model training.
    """
    line = line.lower().replace('--', '—').replace(' - ', ' — ')
    line = quot_re.sub('"', line)
    line = beforedash_re.sub(r'\1— \2', afterdash_re.sub(r'\1 —\2', line))
    line = beforepunc_re.sub(r'\1 \2', afterpunc_re.sub(r'\1 \2', line))
    line = numfix_re.sub(r'\1\2', line)
    return line.lower()

if __name__ == "__main__":
    with open(sys.argv[1], 'r', encoding='utf-8') as ifile,\
         open(sys.argv[2], 'w', encoding='utf-8') as ofile:
        for line in ifile:
            ofile.write(normalize(line))
