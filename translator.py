#! /usr/bin/python3

import re, sys, os, pipes
import kenlm
from math import exp
from tools.pipelines import oneMoreTranslator
from tools.simpletok import normalize
from twlearner import validate_config, get_options, load_rules, make_prefix, tag_corpus
from lxml import etree as ET
from tinydb import TinyDB, Query


default_confname = 'default.ini'

# regular expression to cut out a sentence 
sent_re = re.compile('.*?<sent>\$|.+?$')

# anything between $ and ^
inter_re = re.compile(r'\$.*?\^')

# apertium token (anything between ^ and $)
apertium_token_re = re.compile(r'\^(.*?)\$')

whitespace_re = re.compile('\s')


def search_ambiguous(ambiguous_rules, coverage):
    """
    Look for patterns covered by one of the ambiguous rules in ambiguous_rules.
    If found, return the rules and their patterns.
    """
    pattern_list = []

    for i, part in enumerate(coverage):
        if part[1] in ambiguous_rules:
            options = sorted(list(set(ambiguous_rules[part[1]])))

            for rule in options:
                pattern_list.append((i, (part[0], rule)))

    return pattern_list


def detect_ambiguous(corpus, prefix, 
                     cat_dict, pattern_FST, ambiguous_rules,
                     tixfname, binfname, rule_id_map):

    all_sentences = {}

    with open(corpus, 'r', encoding='utf-8') as file:
        for line in file:
            # look at each sentence in line
            for sent_match in sent_re.finditer(line.strip()):
                all_coverages = []
                coverage_list = pattern_FST.get_lrlm(sent_match.group(0), cat_dict)

                if coverage_list != []:
                    for coverage_item in coverage_list:
                        all_coverages.append(coverage_item)
                         
                        pattern_list = search_ambiguous(ambiguous_rules, coverage_item)

                        if pattern_list != []:
                            for pattern in pattern_list[1:]:
                                new_coverage_item = coverage_item[::] #wtf

                                for i in range(len(new_coverage_item)):
                                    if new_coverage_item[i] == pattern_list[0][1]:
                                        new_coverage_item[i] = pattern[1]

                                all_coverages.append(new_coverage_item)

                if sent_match.group(0) != '^.<sent>$': 
                    all_sentences[sent_match.group(0)] = all_coverages
    
    return all_sentences


def create_custom_t1x(coverage, orig_t1x, temp_t1x, temp_t1x_bin):
    transtree = ET.parse(orig_t1x)
    root = transtree.getroot()

    cats = root.find('section-def-cats')
    attrs = root.find('section-def-attrs')
    varrs = root.find('section-def-vars')
    lists = root.find('section-def-lists')
    macros = root.find('section-def-macros')
    rules = root.find('section-rules').findall('rule')

    root = ET.fromstring('<transfer default="chunk"></transfer>')

    root.append(cats)
    root.append(attrs)
    root.append(varrs)
    root.append(lists)
    root.append(macros)

    section_rules = ET.SubElement(root, 'section-rules')
    rule_nums = []

    for elem in coverage:
        if elem[1] != 'unknown' and elem[1] != 'default':
            rule_nums.append(int(elem[1]))

    for elem in sorted(rule_nums):
        section_rules.append(rules[elem])

    ET.ElementTree(root).write('/home/deltamachine/Desktop/tmp.t1x', pretty_print=True, encoding='utf-8', xml_declaration=True)

    os.system('apertium-preprocess-transfer /home/deltamachine/Desktop/tmp.t1x /home/deltamachine/Desktop/tmp.t1x.bin')


def translate_and_score_sentences(all_sentences, orig_t1x, temp_t1x, temp_t1x_bin, model, table):
    translator = oneMoreTranslator()

    for sentence in all_sentences.keys():
        all_probs = 0
        options = []

        for coverage in all_sentences[sentence]:
            create_custom_t1x(coverage, orig_t1x, temp_t1x, temp_t1x_bin)

            translation = translator.translate(sentence)
            translation = normalize(translation)
            prob = exp(model.score(translation, bos = True, eos = True))
            all_probs += prob
            options.append([coverage, translation, prob])

        for elem in options:
            with open(table, 'a', encoding='utf-8') as file:
                file.write('%s\t%s\t%s\t%s\t%s\n' % (sentence, elem[0], elem[1], elem[2], elem[2] / all_probs))


def learn(config):
    """
    Learn rule weights from monolingual corpus
    using pretrained language model.
    """
    prefix = make_prefix(config)

    # tag corpus
    tagged_fname = tag_corpus(config.get('APERTIUM', 'pair data'), 
                              config.get('DIRECTION', 'source'),
                              config.get('DIRECTION', 'target'), 
                              config.get('LEARNING', 'source corpus'),
                              prefix,
                              config.get('LEARNING', 'data'))

    # load rules, build rule FST
    tixbasepath, binbasepath, cat_dict, pattern_FST, \
    ambiguous_rules, rule_id_map, rule_xmls = \
                            load_rules(config.get('APERTIUM', 'pair data'),
                                       config.get('DIRECTION', 'source'), 
                                       config.get('DIRECTION', 'target'))

    all_sentences = detect_ambiguous(tagged_fname, prefix, cat_dict, pattern_FST,
                                                  ambiguous_rules,
                                                  tixbasepath, binbasepath,
                                                  rule_id_map)

    orig_t1x = config.get('LEARNING', 'original t1x')
    temp_t1x = config.get('LEARNING', 'temporary t1x')
    temp_t1x_bin = config.get('LEARNING', 'temporary t1x.bin')
    model = kenlm.Model(config.get('LEARNING', 'language model'))   
    table = config.get('LEARNING', 'final table') 

    translate_and_score_sentences(all_sentences, orig_t1x, temp_t1x, temp_t1x_bin, model, table)


if __name__ == "__main__":
    confname = get_options()

    if confname is not None:
        config = validate_config(confname)
    else:
        config = validate_config(default_confname)

    learn(config)
