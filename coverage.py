#! /usr/bin/python3

import re, sys
from optparse import OptionParser, OptionGroup
from time import clock

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

def process_line(line, cat_dict):
    """
    Get line in stream format and print all coverages and LRLM only.
    """
    line = get_cats_by_line(line, cat_dict)
    print(line)

    return line

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

def get_rules(transtree):
    """
    From xml tree with transfer rules,
    build an improvised pattern FST using nested dictionaries.
    """
    root = transtree.getroot()
    rules = []
    rule_id_map = {}
    ambiguous_rule_groups = {}
    prev_pattern, rule_group = [], -1
    for i, rule in enumerate(root.find('section-rules').findall('rule')):
        if 'id' in rule.attrib:
            rule_id_map[str(i)] = rule.attrib['id']
        pattern = ['start']
        for pattern_item in rule.find('pattern').findall('pattern-item'):
            pattern.append(pattern_item.attrib['n'])
        if pattern == prev_pattern:
            ambiguous_rule_groups.setdefault(str(rule_group), {str(rule_group)})
            ambiguous_rule_groups[str(rule_group)].add(str(i))
        else:
            rules.append(tuple(pattern) + (str(i),))
            rule_group = i
        prev_pattern = pattern

    rules.sort()
    return rules, ambiguous_rule_groups, rule_id_map

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
    rules, ambiguous_rules, rule_id_map = get_rules(transtree)

    return cat_dict, rules, ambiguous_rules, rule_id_map

class FST:
    def __init__(self, init_rules):
        self.start_state = 0
        self.final_states = {}
        self.states = {0}
        self.alphabet = set()
        self.transitions = {}

        maxlen = max(len(rule) for rule in init_rules) - 1
        self.maxlen = maxlen - 1
        state, prev = 0, ''

        rules = []
        for rule in init_rules:
            rules.append([(rule[0], 0)] + list(rule[1:]))

        for level in range(1, maxlen):
            for rule in rules:
                # end of the rule
                if len(rule) <= level:
                    state += 1
                elif len(rule) == level+1:
                    self.final_states[rule[level-1][1]] = rule[level]
                else:
                    if rule[level] != prev:
                        state += 1
                    self.transitions[(rule[level-1][1], rule[level])] = state
                    prev = rule[level]
                    rule[level] = (rule[level], state)
            prev = ''

    def get_lrlm(self, line, cat_dict):
        line = get_cats_by_line(line, cat_dict)
        coverage_list, state_list = [[]], [self.start_state]
        for token, cat_list in line:
            new_coverage_list, new_state_list = [], []
            for cat in cat_list:
                for coverage, state in zip(coverage_list, state_list):
                    if (state, cat) not in self.transitions:
                        if state in self.final_states:
                            if (self.start_state, cat) in self.transitions:
                                new_coverage_list.append(coverage + [('r', self.final_states[state]), ('w', token)])
                                new_state_list.append(self.transitions[(self.start_state, cat)])
                            else:
                                # discard coverage
                                pass
                                #print('Unknown transition: ({}, {})'.format(state, cat))
                        else:
                            # discard coverage
                            pass
                            #print('Unknown transition: ({}, {})'.format(state, cat))
                    else:
                        new_coverage_list.append(coverage + [('w', token)])
                        new_state_list.append(self.transitions[(state, cat)])
            coverage_list, state_list = new_coverage_list, new_state_list

        new_coverage_list = []
        for coverage, state in zip(coverage_list, state_list):
            if state in self.final_states:
                new_coverage_list.append(coverage + [('r', self.final_states[state])])
            else:
                # discard coverage
                pass
                #print('Unexpected end of pattern')

        if new_coverage_list == []:
            return []

        handsome_coverage_list = []
        for coverage in new_coverage_list:
            pattern, handsome_coverage = [], []
            for element in coverage:
                if element[0] == 'w':
                    pattern.append(element[1])
                else:
                    handsome_coverage.append((pattern, element[1]))
                    pattern = []
            handsome_coverage_list.append(handsome_coverage)

        handsome_coverage_list.sort(key=signature, reverse=True)
        signature_max = signature(handsome_coverage_list[0])
        LRLM_list = []
        for coverage in handsome_coverage_list:
            if signature(coverage) == signature_max:
                LRLM_list.append(coverage)
            else:
                return LRLM_list
        return LRLM_list

def signature(coverage):
    """
    Get coverage signature which is just a tuple
    of lengths of groups comprising the coverage.
    """
    return tuple([len(group[0]) for group in coverage])

if __name__ == "__main__":
    opts, args = get_options()
    cat_dict, rules, ambiguous_rules, rule_id_map = prepare(opts.rfname)
    pattern_FST = FST(rules)

    #for rule in rules:
    #    print(rule)
    #print(rule_id_map)

    coverages = pattern_FST.get_lrlm('^proud<adj><sint><comp>$ ^culture<n><pl>$', cat_dict)
    for coverage in coverages:
        print(coverage)

    sys.exit(0)

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
