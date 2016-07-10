#! /usr/bin/python3

import sys

try: # see if lxml is installed
    from lxml import etree as ET
    print("Using lxml library happily ever after.")
except ImportError: # it is not
    import xml.etree.ElementTree as ET
    print("lxml library not found. Falling back to xml.etree,\n"
          "though it's highly recommended that you install lxml\n"
          "as it works dramatically faster than xml.etree.")

def list_rules(rfname):
    """
    List rules.
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

    root = transtree.getroot()
    for rnum, rule in enumerate(root.find('section-rules').findall('rule')):
        print(rnum, rule.attrib['comment'])
        print(' '.join(pattern_item.attrib['n'] for pattern_item in rule.find('pattern').findall('pattern-item')))
        print()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(1)
    list_rules(sys.argv[1])
