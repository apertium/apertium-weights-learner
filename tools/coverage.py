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

# regex lines to build up rexes for cat-items
any_tag_re = '<[a-z0-9-]+>'
any_num_of_any_tags_re = '({})*'.format(any_tag_re)

# apertium token (anything between ^ and $)
apertium_token_re = re.compile(r'\^(.*?)\$')

def cat_item_to_re(cat_item):
    """
    Get a pattern as specified in xml.
    Output a regex line that matches what 
    is specified by the pattern.

    Attention: ^ and $ here are NOT Apertium start
    and end of token, they are regex start and end
    of line. Token is assumed to have been already
    stripped of its ^ and $.
    """

    # start with the lemma (or with the lack of it)
    re_line = '^' + cat_item.attrib.get('lemma', '[^<>]*')

    tags = cat_item.attrib['tags']

    if tags == '':
        # no tags: close regex line
        return re_line + '$'

    tag_sequence = tags.split('.')
    for tag in tag_sequence[:-1]:
        if tag == '*':
            # any tag
            re_line += any_tag_re
        else:
            # specific tag
            re_line += '<{}>'.format(tag)

    if tag_sequence[-1] == '*':
        # any tags at the end
        re_line += any_num_of_any_tags_re
    else:
        # specific tag at the end
        re_line += '<{}>'.format(tag_sequence[-1])

    return re_line + '$'

def get_cat_dict(transtree):
    """
    Get an xml tree with transfer rules.
    Build an inverted index of the rules.
    """
    root = transtree.getroot()
    cat_dict = {}
    for def_cat in root.find('section-def-cats').findall('def-cat'):
        for cat_item in def_cat.findall('cat-item'):
            # make a regex line to recognize lemma-tag pattern
            re_line = cat_item_to_re(cat_item)
            # add empty category list if there is none
            cat_dict.setdefault(re_line, [])
            # add category to the list
            cat_dict[re_line].append(def_cat.attrib['n'])
    return cat_dict

def get_cats_by_line(line, cat_dict):
    """
    Return all possible categories for each apertium token in line.
    """
    return [get_cat(token, cat_dict)
                for token in apertium_token_re.findall(line)]

def get_cat(token, cat_dict):
    """
    Return all possible categories for token.
    """
    token_cat_list = []
    for cat_re, cat_list in cat_dict.items():
        if re.match(cat_re, token):
            token_cat_list.extend(cat_list)
    return (token, token_cat_list)

def get_rules(transtree):
    """
    From xml tree with transfer rules,
    get rules, ambiguous rules,
    and rule id to number map.
    """
    root = transtree.getroot()

    # build pattern -> rules numbers dict (rules_dict),
    # and rule number -> rule id dict (rule_id_map)
    rules_dict, rule_xmls, rule_id_map  = {}, {}, {}
    for i, rule in enumerate(root.find('section-rules').findall('rule')):
        if 'id' in rule.attrib:
            # rule has 'id' attribute: add it to rule_id_map
            rule_id_map[str(i)] = rule.attrib['id']
            rule_xmls[str(i)] = rule
        # build pattern
        pattern = tuple(pattern_item.attrib['n'] 
                for pattern_item in rule.find('pattern').findall('pattern-item'))
        # add empty rules list for pattern
        # if pattern was not in rules_dict
        rules_dict.setdefault(pattern, [])
        # add rule number to rules list
        rules_dict[pattern].append(str(i))

    # detect groups of ambiguous rules,
    # and prepare rules for building FST
    rules, ambiguous_rule_groups = [], {}
    for pattern, rule_group in rules_dict.items():
        if all(rule in rule_id_map for rule in rule_group):
            # all rules in group have ids: add group to ambiguous rules
            ambiguous_rule_groups[rule_group[0]] = rule_group
        # add pattern to rules using first rule as default
        rules.append(pattern + (rule_group[0],))
    # sort rules to optimize FST building
    rules.sort()

    return rules, ambiguous_rule_groups, rule_id_map, rule_xmls

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
    rules, ambiguous_rules, rule_id_map, rule_xmls = get_rules(transtree)

    return cat_dict, rules, ambiguous_rules, rule_id_map, rule_xmls

class FST:
    """
    FST for coverage recognition.
    """
    def __init__(self, init_rules):
        """
        Initialize with patterns from init_rules.
        """
        self.start_state = 0
        self.final_states = {} # final state: rule
        self.transitions = {} # (state, input): state

        maxlen = max(len(rule) for rule in init_rules)
        self.maxlen = maxlen - 1

        # make rule table, where each pattern starts with ('start', 0)
        rules = [[('start', self.start_state)] + list(rule) for rule in init_rules]

        state, prev_cat = self.start_state, ''
        # look at each rule pattern at fixed position 
        for level in range(1, maxlen):
            for rule in rules:
                if len(rule) <= level:
                    # this rule already ended: increment state to keep it simple
                    state += 1
                elif len(rule) == level+1:
                    # end of the rule is here: add this state as a final
                    self.final_states[rule[level-1][1]] = rule[level]
                else:
                    if rule[level] != prev_cat:
                        # rule patterns diverged: add new state                        
                        state += 1
                    # add transition
                    self.transitions[(rule[level-1][1], rule[level])] = state
                    prev_cat = rule[level]
                    # add current state to current pattern element
                    rule[level] = (rule[level], state)
            # change prev_cat to empty at the end of rules list
            # to ensure state is changed at the start of next run through
            prev_cat = ''

    def get_lrlm(self, line, cat_dict):
        """
        Build all lrlm coverages for line.
        
        """
        # tokenize line and get all possible categories for each token
        line = get_cats_by_line(line, cat_dict)

        # coverage and state lists are built dinamically
        # each state from state_list is the state of FST
        # at the end of corresponding coverage from coverage_list
        coverage_list, state_list = [[]], [self.start_state]

        # go through all tokens in line
        for token, cat_list in line:
            new_coverage_list, new_state_list = [], []

            # go through all cats for the token
            for cat in cat_list:

                # try to continue each coverage obtained on the previous step
                for coverage, state in zip(coverage_list, state_list):

                    # first, check if we can go further along current pattern
                    if (state, cat) in self.transitions:
                        # current pattern can be made longer: add one more token
                        new_coverage_list.append(coverage + [('w', token)])
                        new_state_list.append(self.transitions[(state, cat)])

                    # if not, check if we can finalize current pattern
                    elif state in self.final_states:
                        # current state is one of the final states: close previous pattern
                        new_coverage = coverage + [('r', self.final_states[state])]

                        if (self.start_state, cat) in self.transitions:
                            # can start new pattern
                            new_coverage_list.append(new_coverage + [('w', token)])
                            new_state_list.append(self.transitions[(self.start_state, cat)])
                        elif '*' in token:
                            # can not start new pattern because of an unknown word
                            new_coverage_list.append(new_coverage + [('w', token), ('r', 'unknown')])
                            new_state_list.append(self.start_state)

                    # if not, check if it is just an unknown word
                    elif state == self.start_state and '*' in token:
                        # unknown word at start state: add it to pattern, start new
                        new_coverage_list.append(coverage + [('w', token), ('r', 'unknown')])
                        new_state_list.append(self.start_state)

                    # if nothing worked, just discard this coverage

            coverage_list, state_list = new_coverage_list, new_state_list

        # finalize coverages
        new_coverage_list = []
        for coverage, state in zip(coverage_list, state_list):
            if state in self.final_states:
                # current state is one of the final states: close the last pattern
                new_coverage_list.append(coverage + [('r', self.final_states[state])])
            elif coverage != [] and coverage[-1][0] == 'r':
                # the last pattern is already closed
                new_coverage_list.append(coverage)
            # if nothing worked, just discard this coverage as incomplete

        if new_coverage_list == []:
            # no coverages detected: no need to go further
            return []

        # convert coverage representation:
        # [('r'/'w', rule_number/token), ...] -> [([token, token, ... ], rule_number), ...]
        formatted_coverage_list = []
        for coverage in new_coverage_list:
            pattern, formatted_coverage = [], []
            for element in coverage:
                if element[0] == 'w':
                    pattern.append(element[1])
                else:
                    formatted_coverage.append((pattern, element[1]))
                    pattern = []
            formatted_coverage_list.append(formatted_coverage)

        # now we filter out some not-lrlm coverages
        # that still got into

        # sort coverages by signature, which is a tuple
        # of coverage part lengths
        formatted_coverage_list.sort(key=signature, reverse=True)
        signature_max = signature(formatted_coverage_list[0])

        # keep only those with top signature
        # they would be the LRLM ones
        LRLM_list = []
        for coverage in formatted_coverage_list:
            if signature(coverage) == signature_max:
                # keep adding
                LRLM_list.append(coverage)
            else:
                # no need to look further, others will be worse
                return LRLM_list
        return LRLM_list

def signature(coverage):
    """
    Get coverage signature which is just a tuple
    of lengths of groups comprising the coverage.
    """
    return tuple([len(group[0]) for group in coverage])

if __name__ == "__main__":
    cat_dict, rules, ambiguous_rules, rule_id_map, rule_xmls = prepare(sys.argv[1])
    pattern_FST = FST(rules)

    coverages = pattern_FST.get_lrlm('^prpers<prn><subj><p1><mf><pl>$ ^want# to<vbmod><pp>$ ^wait<vblex><inf>$ ^until<cnjadv>$ ^prpers<prn><subj><p1><mf><pl>$ ^can<vaux><past>$ ^offer<vblex><inf>$ ^what<prn><itg><m><sp>$ ^would<vaux><inf>$ ^be<vbser><inf>$ ^totally<adv>$ ^satisfy<vblex><ger>$ ^for<pr>$ ^consumer<n><pl>$^.<sent>$', cat_dict)

    print('Coverages detected:')
    for coverage in coverages:
        print(coverage)
