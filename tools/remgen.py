#! /usr/bin/python3

import sys, os

try: # see if lxml is installed
    from lxml import etree
    if __name__ == "__main__":
        print("Using lxml library.")
        using_lxml = True
except ImportError: # it is not
    import xml.etree.ElementTree as etree
    if __name__ == "__main__":
        print("lxml library not found. Falling back to xml.etree,\n"
              "though it's highly recommended that you install lxml\n"
              "as it works dramatically faster than xml.etree.")
        using_lxml = False

usage_line = 'Usage: python3 remgen.py INPUT_FILE [OUTPUT_FILE]'

def remove_generalized(using_lxml, ifname, ofname=None):
    """
    Remove generalized patterns (i.e., the ones without lemmas)
    from ifname xml weights file and output new tree to ofname.
    """
    try:
        root = etree.parse(ifname).getroot()
    except etree.ParseError:
        print('Error parsing weights file \'{}\'. '
              'Is there something wrong with it?'.format(opts.rfname))
        return None

    if ofname is None:
        ofname = ifname.rsplit('.', maxsplit=1)[0] + '-remgen.w1x'

    for et_rule_group in root.findall('rule-group'):
        for et_rule in et_rule_group.findall('rule'):
            for et_pattern in et_rule.findall('pattern'):
                remove = False
                for et_pattern_item in et_pattern.findall('pattern-item'):
                    remove = remove or (et_pattern_item.attrib.get('lemma', '') == '')
                if remove:
                    et_rule.remove(et_pattern)

    if using_lxml:
        etree.ElementTree(root).write(ofname, pretty_print=True, encoding='utf-8', xml_declaration=True)
    else:
        etree.ElementTree(root).write(ofname, encoding='utf-8', xml_declaration=True)

    return ofname

if __name__ == "__main__":
    if len(sys.argv) == 1:
        print(usage_line)
        sys.exit(1)

    ifname = sys.argv[1]
    if not os.path.exists(ifname):
        print('Input file not found')
        sys.exit(1)

    if len(sys.argv) == 2:
        remove_generalized(using_lxml, ifname)
    else:
        remove_generalized(using_lxml, ifname, sys.argv[2])
