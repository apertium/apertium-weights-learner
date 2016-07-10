#! /usr/bin/python3

import re, sys
from optparse import OptionParser, OptionGroup

try: # see if lxml is installed
    from lxml import etree as ET
    if __name__ == "__main__":
        print("Using lxml library happily ever after.")
except ImportError: # it is not
    import xml.etree.ElementTree as ET
    if __name__ == "__main__":
        print("lxml library not found. Falling back to xml.etree,\n"
              "though it's highly recommended that you install lxml\n"
              "as it works dramatically faster than xml.etree.")

any_tag_re = '<[a-z0-9-]+>'
any_num_of_any_tags_re = '({})*'.format(any_tag_re)
any_num_of_any_tags_line_re = '^{}$'.format(any_num_of_any_tags_re)
default_cat = ['default']

def tag_pattern_to_re(tag_pattern):
    """
    Get a tag pattern as specified in xml.
    Output a regex line that matches what 
    is specified by the pattern.
    """
    if tag_pattern == '': # no tags
        return '^$'
    re_line = '^'
    tag_sequence = tag_pattern.split('.')
    for tag in tag_sequence[:-1]:
        # any tag
        if tag == '*':
            re_line = re_line + any_tag_re
        # specific tag
        else:
            re_line = re_line + '<{}>'.format(tag)
    # any tags at the end
    if tag_sequence[-1] == '*':
        re_line = re_line + any_num_of_any_tags_re
    # specific tag at the end
    else:
        re_line = re_line + '<{}>'.format(tag_sequence[-1])
    return re_line + '$'

def get_cat_dict(transtree):
    """
    Get an xml with transfer rules.
    Build a makeshift inverted index of the rules.
    """
    root = transtree.getroot()
    cat_dict = {}
    for def_cat in root.find('section-def-cats').findall('def-cat'):
        for cat_item in def_cat.findall('cat-item'):
            tag_re = tag_pattern_to_re(cat_item.attrib.get('tags', '*'))
            lemma = cat_item.attrib.get('lemma', '')
            if tag_re not in cat_dict:
                cat_dict[tag_re] = {}
            if lemma not in cat_dict[tag_re]:
                cat_dict[tag_re][lemma] = []
            cat_dict[tag_re][lemma].append(def_cat.attrib['n'])
    return cat_dict

def get_cats_by_line(line, cat_dict):
    """
    Return all possible categories for ALU.
    """
    return [get_cats_by_ALU(ALU, cat_dict)
                for ALU in re.findall(r'\^.*?\$', line)]

def get_cats_by_ALU(ALU, cat_dict):
    """
    Return set of all possible categories for ALU.
    """
    divided = ALU.lstrip('^').rstrip('$').split('/')
    if len(divided) > 1:
        lemma = divided[0]
        LU_list = divided[1:]
        return (lemma, set(sum([get_cats_by_LU(LU, cat_dict, lemma) 
                                    for LU in LU_list], [])))
    if len(divided) == 1:
        lemma = divided[0] #.split('<', 1)[0]
        return (lemma, set(get_cats_by_LU(divided[0], cat_dict, lemma)))
    return ('default', set(default_cat))

def get_cats_by_LU(LU, cat_dict, lemma):
    """
    Return list of all possible categories for LU.
    """
    partial_lemma = LU.split('<', 1)[0]
    tags = LU[len(partial_lemma):].split('#', 1)[0]
    cat_list = []
    for tag_re in cat_dict:
        if re.match(tag_re, tags):
            cat_list.extend((cat_dict[tag_re].get(lemma, [])))
            cat_list.extend((cat_dict[tag_re].get('', [])))
    if cat_list:
        return cat_list
    return default_cat

def get_pattern_FST(transtree):
    """
    From xml tree with transfer rules,
    build an improvised pattern FST using nested dictionaries.
    """
    root = transtree.getroot()
    pattern_FST = [{}, None]
    ambiguous_rules = {}
    for i, rule in enumerate(root.find('section-rules').findall('rule')):
        curr_level = pattern_FST
        for pattern_item in rule.find('pattern').findall('pattern-item'):
            item_cat = pattern_item.attrib['n']
            if not item_cat in curr_level[0]:
                curr_level[0][item_cat] = [{}, None]
            curr_level = curr_level[0][item_cat]
        if curr_level[1] is not None:
            # the rule is ambiguous as the pattern has already been seen
            ambiguous_rules.setdefault(curr_level[1][0], [(curr_level[1][0], curr_level[1][2])])
            ambiguous_rules[curr_level[1][0]].append((str(i), rule.attrib.get('id', '')))
        else:
            curr_level[1] = (str(i), rule.attrib.get('comment', ''), rule.attrib.get('id', ''))
    return pattern_FST, ambiguous_rules

def rebuild_pattern_r(pattern_FST):
    """
    Recursively rebuild all patterns from pattern FST, just in case.
    """
    rule_list = []
    if pattern_FST[0] != {}:
        for pattern_item in pattern_FST[0]:
            pattern_list = [[pattern_item] + pattern_tail 
                for pattern_tail in rebuild_pattern_r(pattern_FST[0][pattern_item])]
            rule_list.extend(pattern_list)
    if pattern_FST[1] is not None:
        rule_list.append([pattern_FST[1]])
    return rule_list

def output_patterns(pattern_FST):
    """
    Output all patterns to file in linear fashion.
    """
    pattern_list = rebuild_pattern_r(pattern_FST)
    pattern_list.sort(key=lambda x: int(x[-1][0]))
    with open('rules.txt', 'w', encoding='utf-8') as rfile:
        for pattern in pattern_list:
            rfile.write('{: <4}\n  {}\n  {}\n'.format(pattern[-1][0], ' '.join(pattern[:-1]), pattern[-1][1]))

def calculate_coverage_r(pattern_FST, line, state):
    """
    Recursively find all possible pattern combinations
    for preprocessed line where each word has a list
    of categories assigned to it.
    
    Output is a list of lists, each list consists
    of elements of (type, word/num, cat/comm),
    where type is either 'w' (word) or 'r' (rule).
    
    If type is 'w' then the next two items are the word
    and the category assigned to it respectively.

    If type is 'r' then the next two items are the rule
    number and its commentary from the xml representation.

    The rule entry in the list marks the end of pattern
    for this rule.

    line is current line with ambiguous categories assigned
    to words, state is a state of our makeshift FST represented
    by its level.
    """
    # the end of the line
    if not line:
        # check if it's also the end of pattern
        if state[1] is not None:
            return [[('r',) + state[1]]]
        return []

    coverage_list = []
    current_item = line[0]

    # continue the pattern for each category assigned to current word
    for cat in (current_item[1] & set(state[0].keys())):
        pattern_list = [[('w', current_item[0], cat)] + pattern_tail 
                            for pattern_tail 
                                in calculate_coverage_r(
                                        pattern_FST,
                                        line[1:],
                                        state[0][cat])]
        coverage_list.extend(pattern_list)

    # check if it can be an end of the pattern
    if state[1] is not None:
        # if so, also try to start new pattern from here
        pattern_list = [[('r',) + state[1]] + pattern_tail 
                            for pattern_tail 
                                in calculate_coverage_r(
                                        pattern_FST, 
                                        line, 
                                        pattern_FST)]
        coverage_list.extend(pattern_list)
    return coverage_list

def parse_coverage_list(coverage_list):
    """
    Get list of lists representing coverages
    (as output by calculate_coverage_r) and return
    a list of regrouped coverages.
    """
    return [parse_coverage(coverage) for coverage in coverage_list]

def parse_coverage(coverage):
    """
    Get a list representing one coverage
    (as output by calculate_coverage_r) and return
    a list where elements are groups (list_of_words, rule).
    """
    groups = []
    current_group = []
    for token in coverage:
        if token[0] == 'w':
            current_group.append(token[1])
        elif token[0] == 'r':
            groups.append((current_group, token[1:]))
            current_group = []
    return groups

def coverages_to_groups(coverage_list):
    output_list = []
    for coverage in coverage_list:
        output_list.append(coverage_to_groups(coverage))
    return output_list

def output_all_coverages(coverage_list, output_stream):
    for coverage in coverage_list:
        output_stream.write(coverage_to_groups(coverage) + '\n')
    output_stream.write('\n')

def coverage_to_groups(coverage):
    """
    Output coverage with groups.
    """
    output_str = '' 
    for group in coverage:
        output_str = output_str + \
            ' ({} {})'.format(group[1][0], ' '.join(group[0]))
    return output_str.strip()

def signature(coverage):
    """
    Get coverage signature which is just a tuple
    of lengths of groups comprising the coverage.
    """
    return tuple([len(group[0]) for group in coverage])

def get_LRLM(coverage_list):
    """
    Get only LRLM coverages from list of all coverages
    by sorting them lexicographycally by their signatures.
    """
    sorted_list = sorted(coverage_list, key=signature, reverse=True)
    signature_max = signature(sorted_list[0])
    LRLM_list = []
    for item in sorted_list:
        if signature(item) == signature_max:
            LRLM_list.append(item)
        else:
            return LRLM_list
    return LRLM_list

def process_line(line, cat_dict, pattern_FST, output_stream, out_all, out_lrlm, print_out=True):
    """
    Get line in stream format and print all coverages and LRLM only.
    """
    if print_out:
        output_stream.write(line + '\n')
    line = get_cats_by_line(line, cat_dict)
    coverage_list = calculate_coverage_r(pattern_FST, line, pattern_FST)
    parsed_coverages = []
    if coverage_list != []:
        if out_all:
            parsed_coverages = parse_coverage_list(coverage_list)
            if print_out:
                output_stream.write('All coverages:\n')
                output_all_coverages(parsed_coverages, output_stream)
        if out_lrlm:
            parsed_coverages = get_LRLM(parse_coverage_list(coverage_list))
            if print_out:
                output_stream.write('LRLM only:\n')
                output_all_coverages(parsed_coverages, output_stream)
    else:
        if print_out:
            output_stream.write('No coverage found\n')
    return parsed_coverages, line

def get_options():
    """
    Parse commandline arguments
    """
    usage = "USAGE: ./%prog [-a|-l] [-o OUTPUT_FILE] -r RULES_FILE [INPUT_FILE]"
    op = OptionParser(usage=usage)

    op.add_option("-o", "--out", dest="ofname",
                  help="output results to OUTPUT_FILE.", metavar="OUTPUT_FILE")

    op.add_option("-r", "--rules", dest="rfname",
                  help="use RULES_FILE t*x file for calculating coverages.", metavar="RULES_FILE")

    mode_group = OptionGroup(op, "output mode",
                    "Specify what coverages to output, all or LRLM.  "
                    "If none specified, outputs both variants.")

    mode_group.add_option("-a", "--all", dest="all", action="store_true",
                  help="output all coverages")

    mode_group.add_option("-l", "--lrlm", dest="lrlm", action="store_true",
                  help="output LRLM coverages")

    op.add_option_group(mode_group)

    (opts, args) = op.parse_args()

    if opts.rfname is None:
        op.error("specify t*x file containing rules with -r (--rules) option.")
        op.print_help()
        sys.exit(1)

    if len(args) > 1:
        op.error("too many arguments.")
        op.print_help()
        sys.exit(1)

    if opts.all is None and opts.lrlm is None:
        opts.all = True
        opts.lrlm = True

    return opts, args

def prepare(rfname):
    """
    Read transfer file and prepare pattern FST.
    """
    try:
        transtree = ET.parse(rfname)
    except FileNotFoundError:
        print('Failed to locate rules file \'{}\'. '
              'Have you misspelled the name?'.format(opts.rfname))
        sys.exit(1)
    except ET.ParseError:
        print('Error parsing rules file \'{}\'. '
              'Is there something wrong with it?'.format(opts.rfname))
        sys.exit(1)

    cat_dict = get_cat_dict(transtree)
    pattern_FST, ambiguous_rules = get_pattern_FST(transtree)
    #output_patterns(pattern_FST)

    return cat_dict, pattern_FST, ambiguous_rules

if __name__ == "__main__":
    opts, args = get_options()
    cat_dict, pattern_FST, ambiguous_rules = prepare(opts.rfname)

    if len(args) == 0:
        input_stream = sys.stdin
    elif len(args) == 1:
        try:
            input_stream = open(args[0], 'r', encoding='utf-8')
        except FileNotFoundError:
            print('Failed to locate input file \'{}\'. '
                  'Have you misspelled the name?'.format(args[0]))
            sys.exit(1)

    if opts.ofname:
        output_stream = open(opts.ofname, 'w', encoding='utf-8')            
    else:
        output_stream = sys.stdout

    for line in input_stream:
        process_line(line, cat_dict, pattern_FST, output_stream, opts.all, opts.lrlm)

    if opts.ofname:
        output_stream.close()
