#! /usr/bin/python3

import re, sys, os, pipes, gc, hashlib
from time import perf_counter as clock
from math import exp
# language model handling
import kenlm
# simple config in python file
import twlconfig
# module for coverage calculation
from tools import coverage
# apertium translator pipelines
from tools.pipelines import partialTranslator, weightedPartialTranslator
from tools.simpletok import normalize
from tools.prune import prune_xml_transfer_weights

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

tmpweights_fname = 'tmpweights.w1x'

# regular expression to cut out a sentence 
sent_re = re.compile('.*?<sent>\$|.+?$')

# anything between $ and ^
inter_re = re.compile(r'\$.*?\^')

# apertium token (anything between ^ and $)
apertium_token_re = re.compile(r'\^(.*?)\$')

whitespace_re = re.compile('\s')

def load_rules(pair_data, source, target):
    """
    Load t1x transfer rules file from pair_data folder in source-target direction.
    """
    tixbasename = '{}.{}-{}'.format(os.path.basename(pair_data), source, target)
    tixbasepath = os.path.join(pair_data, tixbasename)
    binbasepath = os.path.join(pair_data, '{}-{}'.format(source, target))
    tixfname = '.'.join((tixbasepath, 't1x'))
    cat_dict, rules, ambiguous_rules, rule_id_map, rule_xmls = coverage.prepare(tixfname)
    pattern_FST = coverage.FST(rules)

    return tixbasepath, binbasepath, cat_dict, pattern_FST, ambiguous_rules, rule_id_map, rule_xmls

def make_prefix(corpus, data_folder):
    """
    Make common prefix for all intermediate files.
    """
    trimmed_basename = os.path.splitext(os.path.basename(corpus))[0]
    prefix = os.path.join(data_folder, trimmed_basename)
    return prefix

def tag_corpus(pair_data, source, target, corpus, prefix, data_folder):
    """
    Take source language corpus.
    Tag it but do not translate.
    """
    print('Tagging source corpus.')
    btime = clock()

    # make output file name
    ofname = prefix + '-tagged.txt'

    # create pipeline
    pipe = pipes.Template()
    pipe.append('apertium -d "{}" {}-{}-tagger'.format(pair_data, source, target), '--')
    pipe.append('apertium-pretransfer', '--')
    
    # tag
    pipe.copy(corpus, ofname)

    print('Done in {:.2f}'.format(clock() - btime))    
    return ofname

def search_ambiguous(ambiguous_rules, coverage):
    """
    Look for patterns covered by one of the ambiguous rules in ambiguous_rules.
    If found, return the rules and their patterns.
    """
    pattern_list = []
    for i, part in enumerate(coverage):
        if part[1] in ambiguous_rules:
            pattern_list.append((i, part[1], tuple(part[0])))
    return pattern_list

def detect_ambiguous(corpus, prefix, cat_dict, pattern_FST, ambiguous_rules, tixfname, binfname, rule_id_map):
    """
    Find sentences that contain ambiguous chunks.
    Translate them in all possible ways.
    Store the results.
    """
    print('Looking for ambiguous sentences and translating them.')
    btime = clock()

    # make output file name
    ofname = prefix + '-ambiguous.txt'

    # initialize translators
    # for translation with no weights
    translator = partialTranslator(tixfname, binfname)
    # for weighted translation
    weighted_translator = weightedPartialTranslator(tixfname, binfname)

    # initialize statistics
    lines_count, total_sents_count, ambig_sents_count, ambig_chunks_count = 0, 0, 0, 0
    botched_coverages = 0
    lbtime = clock()

    with open(corpus, 'r', encoding='utf-8') as ifile, \
         open(ofname, 'w', encoding='utf-8') as ofile:
        for line in ifile:

            # look at each sentence in line
            for sent_match in sent_re.finditer(line.strip()):
                if sent_match.group(0) != '':
                    total_sents_count += 1

                # get coverages
                coverage_list = pattern_FST.get_lrlm(sent_match.group(0), cat_dict)
                if coverage_list == []:
                    botched_coverages += 1
                    #print('Botched coverage:', sent_match.group(0))
                    #print()
                else:
                    # look for ambiguous chunks
                    coverage_item = coverage_list[0]
                    pattern_list = search_ambiguous(ambiguous_rules, coverage_item)
                    if pattern_list != []:
                        #print('Coverage:', coverage_item)
                        #print('Pattern list:', pattern_list)
                        #print()
                        ambig_sents_count += 1
                        # segment the sentence into parts each containing one ambiguous chunk
                        sentence_segments, prev = [], 0
                        for i, rule_group_number, pattern in pattern_list:
                            ambig_chunks_count += 1
                            list_with_chunk = sum([chunk[0] 
                                for chunk in coverage_item[prev:i+1]], [])
                            piece_of_line = '^' + '$ ^'.join(list_with_chunk) + '$'
                            sentence_segments.append([rule_group_number, pattern, piece_of_line])
                            prev = i+1

                        if sentence_segments != []:
                            if prev <= len(coverage_item):
                                # add up the tail of the sentence
                                list_with_chunk = sum([chunk[0]
                                    for chunk in coverage_item[prev:]], [])
                                piece_of_line = ' ^' + '$ ^'.join(list_with_chunk) + '$'
                                sentence_segments[-1][2] += piece_of_line

                            #print(sentence_segments)
                            #print()

                            # first, translate each segment with default rules
                            for sentence_segment in sentence_segments:
                                sentence_segment.append(translator.translate(sentence_segment[2]))

                            # second, translate each segment with each of the rules,
                            # and make full sentence, where other segments are translated with default rules
                            for j, sentence_segment in enumerate(sentence_segments):
                                translation_list = translate_ambiguous(weighted_translator, ambiguous_rules[sentence_segment[0]], 
                                                                       sentence_segment[1], sentence_segment[2], rule_id_map)
                                output_list = []
                                for rule, translation in translation_list:
                                    translated_sentence = ' '.join(sentence_segment[3] for sentence_segment in sentence_segments[:j]) +\
                                                          ' ' + translation + ' ' +\
                                                          ' '.join(sentence_segment[3] for sentence_segment in sentence_segments[j+1:])
                                    output_list.append('{}\t{}'.format(rule, translated_sentence.strip(' ')))

                                # store results to a file
                                # first, print rule group number, pattern, and number of rules in the group
                                print('{}\t^{}$\t{}'.format(sentence_segment[0], '$ ^'.join(sentence_segment[1]), len(output_list)), file=ofile)
                                # then, output all the translations in the following way: rule number, then translated sentence
                                print('\n'.join(output_list), file=ofile)

            lines_count += 1
            if lines_count % 100 == 0:
                print('\n{} total lines\n{} total sentences'.format(lines_count, total_sents_count))
                print('{} ambiguous sentences\n{} ambiguous chunks'.format(ambig_sents_count, ambig_chunks_count))
                print('{} botched coverages\nanother {:.4f} elapsed'.format(botched_coverages, clock() - lbtime))
                gc.collect()
                lbtime = clock()

    # clean up temporary weights file
    if os.path.exists(tmpweights_fname):
        os.remove(tmpweights_fname)

    print('Done in {:.2f}'.format(clock() - btime))
    return ofname

def translate_ambiguous(weighted_translator, rule_group, pattern, sent_line, rule_id_map):
    """
    Translate sent_line for each rule in rule_group.
    """
    translation_list = []

    #for each rule
    for focus_rule in rule_group:
        # create weights file favoring that rule
        oroot = etree.Element('transfer-weights')
        et_rulegroup = etree.SubElement(oroot, 'rule-group')
        for rule in rule_group:
            et_rule = make_et_rule(str(rule), et_rulegroup, rule_id_map)
            if rule == focus_rule:
                et_pattern = make_et_pattern(et_rule, pattern)

        if using_lxml:
            etree.ElementTree(oroot).write(tmpweights_fname, pretty_print=True, encoding='utf-8', xml_declaration=True)
        else:
            etree.ElementTree(oroot).write(tmpweights_fname, encoding='utf-8', xml_declaration=True)

        # translate using created weights file
        translation = weighted_translator.translate(sent_line, tmpweights_fname)
        translation_list.append((focus_rule, translation))

    return translation_list

def score_sentences(ambig_sentences_fname, model, prefix):
    """
    Score translated sentences against language model.
    """
    print('Scoring ambiguous sentences.')
    btime, chunk_counter, sentence_counter = clock(), 0, 0

    # make output file name
    ofname = prefix + '-chunk-weights.txt'

    with open(ambig_sentences_fname, 'r', encoding='utf-8') as ifile, \
         open(ofname, 'w', encoding='utf-8') as ofile:
        reading = True
        while reading:
            try:
                line = ifile.readline()
                group_number, pattern, rulecount = line.rstrip('\n').split('\t')
                weights_list, total = [], 0.

                # read and process as much following lines as specified by rulecount
                for i in range(int(rulecount)):
                    line = ifile.readline()
                    rule_number, sentence = line.rstrip('\n').split('\t')

                    # score and add up
                    score = exp(model.score(normalize(sentence), bos = True, eos = True))
                    weights_list.append((rule_number, score))
                    total += score
                    sentence_counter += 1

                # normalize and print out         
                for rule_number, score in weights_list:
                    print(group_number, rule_number, pattern, score / total, sep='\t', file=ofile)
                chunk_counter += 1

            except ValueError:
                reading = False
            except IndexError:
                reading = False
            except EOFError:
                reading = False

    print('Scored {} chunks, {} sentences in {:.2f}'.format(chunk_counter, sentence_counter, clock() - btime))
    return ofname

def make_et_pattern(et_rule, tokens, weight=1.):
    """
    Make pattern element for xml tree
    with pattern-item elements.
    """
    if type(tokens) == type(''):
        # if tokens is str, tokenize it
        tokens = apertium_token_re.findall(tokens)
    et_pattern = etree.SubElement(et_rule, 'pattern')
    et_pattern.attrib['weight'] = str(weight)
    for token in tokens:
        et_pattern_item = etree.SubElement(et_pattern, 'pattern-item')
        parts = token.split('<', maxsplit=1) + ['']
        lemma, tags = parts[0], parts[1].strip('>').replace('><', '.')
        et_pattern_item.attrib['lemma'] = lemma
        et_pattern_item.attrib['tags'] = tags
    return et_pattern

def make_et_rule(rule_number, et_rulegroup, rule_map, rule_xmls=None):
    """
    Make rule element for xml tree.
    """
    et_rule = etree.SubElement(et_rulegroup, 'rule')
    if rule_xmls is not None:
        # this part is used for final weights file
        # copy rule attributes from transfer file
        et_rule.attrib.update(rule_xmls[rule_number].attrib)
        # calculate md5 sum of rule text without whitespace
        # and add it as rule attribute
        rule_text = etree.tostring(rule_xmls[rule_number], encoding='unicode')
        clean_rule_text = whitespace_re.sub('', rule_text)
        et_rule.attrib['md5'] = hashlib.md5(clean_rule_text.encode()).hexdigest()
    else:
        # this part is used for temporary weights file
        et_rule.attrib['id'] = rule_map[rule_number]
    return et_rule

def make_xml_transfer_weights(scores_fname, prefix, rule_map, rule_xmls):
    """
    Sum up the weights for each rule-pattern pair,
    add the result to xml weights file.
    """
    print('Summing up the weights and making xml rules.')
    btime = clock()

    # make output file names
    sorted_scores_fname = prefix + '-chunk-weights-sorted.txt'
    ofname = prefix + '-rule-weights.w1x'

    # create pipeline
    pipe = pipes.Template()
    pipe.append('sort $IN > $OUT', 'ff')
    pipe.copy(scores_fname, sorted_scores_fname)

    # create empty output xml tree
    oroot = etree.Element('transfer-weights')
    et_newrulegroup = etree.SubElement(oroot, 'rule-group')

    with open(sorted_scores_fname, 'r', encoding='utf-8') as ifile:
        # read and process the first line
        prev_group_number, prev_rule_number, prev_pattern, weight = ifile.readline().rstrip('\n').split('\t')
        total_pattern_weight = float(weight)
        et_newrule = make_et_rule(prev_rule_number, et_newrulegroup, rule_map, rule_xmls)

        # read and process other lines
        for line in ifile:
            group_number, rule_number, pattern, weight = line.rstrip('\n').split('\t')
            if group_number != prev_group_number:
                # rule group changed: flush pattern, close previuos, open new
                et_newpattern = make_et_pattern(et_newrule, prev_pattern, total_pattern_weight)
                et_newrulegroup = etree.SubElement(oroot, 'rule-group')
                et_newrule = make_et_rule(rule_number, et_newrulegroup, rule_map, rule_xmls)
                total_pattern_weight = 0.
            elif rule_number != prev_rule_number:
                # rule changed: flush previous pattern, create new rule
                et_newpattern = make_et_pattern(et_newrule, prev_pattern, total_pattern_weight)
                et_newrule = make_et_rule(rule_number, et_newrulegroup, rule_map, rule_xmls)
                total_pattern_weight = 0.
            elif pattern != prev_pattern:
                # pattern changed: flush previous
                et_newpattern = make_et_pattern(et_newrule, prev_pattern, total_pattern_weight)
                total_pattern_weight = 0.
            # add up rule-pattern weights
            total_pattern_weight += float(weight)
            prev_group_number, prev_rule_number, prev_pattern = group_number, rule_number, pattern

        # flush the last rule-pattern
        et_newpattern = make_et_pattern(et_newrule, prev_pattern, total_pattern_weight)

    if using_lxml:
        etree.ElementTree(oroot).write(ofname, pretty_print=True, encoding='utf-8', xml_declaration=True)
    else:
        etree.ElementTree(oroot).write(ofname, encoding='utf-8', xml_declaration=True)

    print('Done in {:.2f}'.format(clock() - btime))
    return ofname

if __name__ == "__main__":
    if not os.path.exists(twlconfig.data_folder):
        os.makedirs(twlconfig.data_folder)
    prefix = make_prefix(twlconfig.source_corpus, twlconfig.data_folder)

    tbtime = clock()

    # tag corpus
    tagged_fname = tag_corpus(twlconfig.apertium_pair_data, 
                              twlconfig.source, twlconfig.target, 
                              twlconfig.source_corpus, prefix,
                              twlconfig.data_folder)

    # load rules, build rule FST
    tixbasepath, binbasepath, cat_dict, pattern_FST, \
    ambiguous_rules, rule_id_map, rule_xmls = \
                            load_rules(twlconfig.apertium_pair_data,
                                       twlconfig.source, twlconfig.target)

    # detect and store sentences with ambiguity
    ambig_sentences_fname = detect_ambiguous(tagged_fname, prefix, 
                                             cat_dict, pattern_FST,
                                             ambiguous_rules,
                                             tixbasepath, binbasepath,
                                             rule_id_map)

    # load language model
    print('Loading language model.')
    btime = clock()
    model = kenlm.Model(twlconfig.language_model)
    print('Done in {:.2f}'.format(clock() - btime))

    # estimate rule weights for each ambiguous chunk
    scores_fname = score_sentences(ambig_sentences_fname, model, prefix)

    # sum up weigths for rule-pattern and make unprunned xml
    weights_fname = make_xml_transfer_weights(scores_fname, prefix, 
                                              rule_id_map, rule_xmls)

    # prune weights file
    prunned_fname = prune_xml_transfer_weights(using_lxml, weights_fname)

    print('Performed in {:.2f}'.format(clock() - tbtime))
