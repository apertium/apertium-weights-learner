#! /usr/bin/python3

import re, sys, os, pipes, math
from optparse import OptionParser, OptionGroup
from subprocess import call
import coverage
import kenlm

# regular expression to cut out a sentence 
sent_re = re.compile('.*?<sent>\$')

weights_head = '<?xml version="1.0" encoding="UTF-8"?>\n<transfer-weights>\n'
weights_tail = '</transfer-weights>'

def get_options():
    """
    Parse commandline arguments
    """
    usage = "USAGE: ./%prog [<option>...] [INPUT_FILE]"
    op = OptionParser(usage=usage)

    op.add_option("-p", "--pair", dest="pfolder",
                  help="language pair data folder. Mandatory.", metavar="PAIR_FOLDER")

    op.add_option("-d", "--direction", dest="direction",
                  help="transfer direction. Mandatory.", metavar="DIRECTION")

    op.add_option("-l", "--lang-model", dest="model",
                  help="path to language model. Mandatory.", metavar="LANG_MODEL")

    op.add_option("-m", "--max-sent", dest="max_sent",
                  help="maximum number of ambiguous sentences.", metavar="MAX_SENT")

    op.add_option("-o", "--out", dest="ofname",
                  help="output results to OUTPUT_FILE.", metavar="OUTPUT_FILE")

    (opts, args) = op.parse_args()

    if opts.pfolder is None:
        op.error("please specify language pair data folder.")
        op.print_help()
        sys.exit(1)

    if opts.direction is None:
        op.error("please specify transfer direction.")
        op.print_help()
        sys.exit(1)

    if opts.model is None:
        op.error("please specify model.")
        op.print_help()
        sys.exit(1)

    if opts.ofname is None:
        op.error("please specify output file.")
        op.print_help()
        sys.exit(1)

    opts.pfolder = opts.pfolder.rstrip('/\\')

    if len(args) > 1:
        op.error("too many arguments.")
        op.print_help()
        sys.exit(1)

    return opts, args

def pattern_to_xml(pattern, weight=1.):
    pattern_line = '      <pattern weight="{}">\n'.format(weight)
    for pattern_item in pattern:
        parts = pattern_item.split('<', maxsplit=1)
        lemma, tags = parts[0], parts[1].strip('>')
        pattern_line += '        <pattern-item lemma="{}" tags="{}"/>\n'.format(lemma, '.'.join(tags.split('><')))
    pattern_line += '      </pattern>\n'
    return pattern_line

def get_weights(rule_group, pattern, sent_line, tixfname, binfname, output_stream):
    total = 0.
    weights_list = []
    
    pattern = pattern_to_xml(pattern)

    for focus_rule in rule_group:
        weights_line = weights_head + '  <rule-group>\n'
        for rule in rule_group:
            weights_line += '    <rule id="{}">\n'.format(rule[1])
            if rule == focus_rule:
                weights_line += pattern
            weights_line += '    </rule>\n'
        weights_line += '  </rule-group>\n' + weights_tail
        with open('tmpweights.w1x', 'w', encoding='utf-8') as wfile:
            wfile.write(weights_line)
        translation = translate(sent_line, tixfname, binfname, 'tmpweights.w1x', output_stream)
        score = model.score(translation.lower(), bos = True, eos = True)
        weights_list.append([translation, math.exp(score), focus_rule[1]])
    for translation, score, rule_id in weights_list:
        total += score
    for score_item in weights_list:
        score_item[1] = score_item[1] / total
        #print(score_item[1], score_item[0])
    return weights_list

def output_final_weights(weights_dict, wfname):
    with open(wfname, 'w', encoding='utf-8') as wfile:
        wfile.write(weights_head)
        for rule_group in weights_dict.values():
            wfile.write('  <rule-group>\n')
            for rule_id, pattern_dict in rule_group.items():
                wfile.write('    <rule id="{}">\n'.format(rule_id))
                for pattern, weight in pattern_dict.items():
                    wfile.write(pattern_to_xml(pattern, weight))
                wfile.write('    </rule>\n')
            wfile.write('  </rule-group>\n')
        wfile.write(weights_tail)            

def translate(sent_line, tixfname, binfname, weightsfname, output_stream):
    pipe = pipes.Template()
    pipe.append('lt-proc -b {}'.format('.'.join((binfname, 'autobil.bin'))), '--')
    pipe.append('apertium-transfer -bw {} {} {}'.format(weightsfname, '.'.join((tixfname, 't1x')), '.'.join((binfname, 't1x.bin'))), '--')
    pipe.append('apertium-interchunk {} {}'.format('.'.join((tixfname, 't2x')), '.'.join((binfname, 't2x.bin'))), '--')
    pipe.append('apertium-postchunk {} {}'.format('.'.join((tixfname, 't3x')), '.'.join((binfname, 't3x.bin'))), '--')
    pipe.append('lt-proc -g {}'.format('.'.join((binfname, 'autogen.bin'))), '--')
    pipe.append('apertium-retxt', '--')

    pipefile = pipe.open('pipefile', 'w')
    pipefile.write(sent_line)
    pipefile.close()
    return open('pipefile').read()

def search_ambiguous(ambiguous_rules, coverage_item):
    """
    Look for a pattern covered by one of ambiguous rules in ambiguous_rules.
    If found, return the rule and the pattern.
    """
    for part in coverage_item:
        if part[1][0] in ambiguous_rules:
            return part[1][0], part[0]
    return None, None

if __name__ == "__main__":
    opts, args = get_options()
    tixfname = os.path.join(opts.pfolder, 
                          '.'.join((os.path.basename(opts.pfolder), opts.direction)))
    binfname = os.path.join(opts.pfolder, opts.direction)
    rfname = '.'.join((tixfname, 't1x'))
    cat_dict, pattern_FST, ambiguous_rules = coverage.prepare(rfname)
    #print(ambiguous_rules)

    weights_dict = {rule_num: {rule[1]: {} for rule in rule_list} for rule_num, rule_list in ambiguous_rules.items()}
    #print(weights_dict)

    if len(args) == 0:
        input_stream = sys.stdin
    elif len(args) == 1:
        try:
            input_stream = open(args[0], 'r', encoding='utf-8')
        except FileNotFoundError:
            print('Failed to locate input file \'{}\'. '
                  'Have you misspelled the name?'.format(args[0]))
            sys.exit(1)

    print('Loading language model... ')
    model = kenlm.Model(opts.model)
    print('done.')

    sentences = []
    sent_count = 0
    if opts.max_sent:
        max_sent_count = int(opts.max_sent)
    else:
        max_sent_count = None

    for line in input_stream:
        line = line.strip()
        for sent_match in sent_re.finditer(line):
            sent_line = sent_match.group(0)
            if '*' not in sent_line:
                coverage_list, parsed_line = coverage.process_line(sent_line,
                                        cat_dict, pattern_FST,
                                        output_stream,
                                        False, True, False)
                # check if any rule in any coverage is ambiguous,
                # take first coverage and first rule if any
                for coverage_item in coverage_list:
                    rule_number, pattern = search_ambiguous(ambiguous_rules, coverage_item)
                    if rule_number is not None:
                        #print('{}\n{}\n'.format(sent_count, sent_line))
                        #for item in parsed_line:
                        #    print(str(item) + '\n')
                        #print(coverage.coverage_to_groups(coverage_item) + '\n\n')
                        weights_list = get_weights(ambiguous_rules[rule_number], pattern, sent_line, tixfname, binfname, output_stream)
                        #print(weights_list)
                        for translation, score, rule_id in weights_list:
                            weights_dict[rule_number][rule_id].setdefault(tuple(pattern), 0.)
                            weights_dict[rule_number][rule_id][tuple(pattern)] += score
                        sent_count += 1
                        if sent_count % 100 == 0:
                            print(sent_count)
                        break
        if max_sent_count is not None and sent_count >= max_sent_count:
            break

    #print(weights_dict)
    output_final_weights(weights_dict, opts.ofname)
