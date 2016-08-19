#! /usr/bin/python3

import sys, os

try: # see if lxml is installed
    from lxml import etree
    if __name__ == "__main__":
        print("Using lxml library happily ever after.")
        using_lxml = True
except ImportError: # it is not
    import xml.etree.ElementTree as etree
    if __name__ == "__main__":
        print("lxml library not found. Falling back to xml.etree,\n"
              "though it's highly recommended that you install lxml\n"
              "as it works dramatically faster than xml.etree.")
        using_lxml = False

usage_line = 'Usage: ./prune.py INPUT_FILE [OUTPUT_FILE]'

def prune_transfer_weights(ifname, ofname):
    """
    Prune the transfer weights file provided in ifname.

    For each rule group:
      for each pattern that is present in more than one rule:
        - keep only the entry in the rule
          with the highest weight, and set the weight to 1
        - if the rule with the entry with weight = 1 happens
          to be the default (first) rule, remove that entry
          from the weights file altogether, since it will be
          the rule applied anyway (in fact, we only want
          to weight exceptions from the default rule).

    Write the result to ofname.
    """
    try:
        iroot = etree.parse(ifname).getroot()
    except etree.ParseError:
        print('Error parsing rules file \'{}\'. '
              'Is there something wrong with it?'.format(opts.rfname))
        sys.exit(1)

    # create (empty) output xml tree
    oroot = etree.Element('transfer-weights')
    # go through rule-groups
    for et_rule_group in iroot.findall('rule-group'):
        # store rule ids in order of their appearance in rule_list
        # store xml rules in xml_rule_dict with ids as keys
        rule_list, xml_rule_dict = [], {}
        # store lists of weights by rule in pattern_rule_dict
        # with pattern strings as keys
        # store xml patterns in xml_pattern_dict with pattern strings as keys
        pattern_rule_dict, xml_pattern_dict = {}, {}
        for et_rule in et_rule_group.findall('rule'):
            rule_id = et_rule.attrib['id']
            rule_list.append(rule_id)
            xml_rule_dict[rule_id] = et_rule.attrib
            for et_pattern in et_rule.findall('pattern'):
                pattern_str = xml_pattern_to_str(et_pattern)
                pattern_rule_dict.setdefault(pattern_str, [])
                pattern_rule_dict[pattern_str].append((rule_id, float(et_pattern.attrib['weight'])))
                xml_pattern_dict[pattern_str] = et_pattern
        # for each pattern, sort its (rule, weight) list by weight
        for pattern, weights_list in pattern_rule_dict.items():
            weights_list.sort(key=lambda x: x[1], reverse=True)
        # the first rule is default and is therefore should contain no patterns
        et_new_rule_group = etree.SubElement(oroot, 'rule-group')
        et_new_rule = etree.SubElement(et_new_rule_group, 'rule')
        et_new_rule.attrib.update(xml_rule_dict[rule_list[0]])
        # go through other rules
        for rule_id in rule_list[1:]:
            et_new_rule = etree.SubElement(et_new_rule_group, 'rule')
            et_new_rule.attrib.update(xml_rule_dict[rule_id])
            for pattern_str, weights_list in pattern_rule_dict.items():
                # if the heaviest weight for the pattern is for this rule...
                if weights_list[0][0] == rule_id:
                    # ... add this pattern to the rule...
                    et_new_pattern = etree.SubElement(et_new_rule, 'pattern')
                    # ...with weight=1.0...
                    et_new_pattern.attrib['weight'] = '1.0'
                    # ...and add all its pattern-elements
                    for et_pattern_item in xml_pattern_dict[pattern_str].findall('pattern-item'):
                        et_new_pattern_item = etree.SubElement(et_new_pattern, 'pattern-item')
                        et_new_pattern_item.attrib.update(et_pattern_item.attrib)

    if using_lxml:
        etree.ElementTree(oroot).write(ofname, pretty_print=True, encoding='utf-8', xml_declaration=True)
    else:
        etree.ElementTree(oroot).write(ofname, encoding='utf-8', xml_declaration=True)

def xml_pattern_to_str(et_pattern):
    """
    Convert xml pattern item into pattern string.
    """
    pattern_item_list = []
    for et_pattern_item in et_pattern:
        pattern_item_str = '^{}'.format(et_pattern_item.attrib['lemma'])
        tags = et_pattern_item.attrib['lemma']
        if tags != '':
            pattern_item_str += '<{}>$'.format(tags.replace('.', '><'))
        else:
            pattern_item_str += '$'
        pattern_item_list.append(pattern_item_str)
    return ' '.join(pattern_item_list)

if __name__ == "__main__":
    if len(sys.argv) == 1:
        print(usage_line)
        sys.exit(1)

    ifname = sys.argv[1]
    if not os.path.exists(ifname):
        print('Input file not found')
        sys.exit(1)

    if len(sys.argv) == 2:
        ofname = ifname.rsplit('.', maxsplit=1)[0] + '-prunned.w1x'
    else:
        ofname = sys.argv[2]
            
    prune_transfer_weights(ifname, ofname)
