#! /usr/bin/python3

import re, sys, os, pipes, gc
from math import exp
import coverage
import kenlm
from time import perf_counter as clock
import twlconfig # a simple config in python file

# regular expression to cut out a sentence 
sent_re = re.compile('.*?<sent>\$')
inter_re = re.compile(r'\$.*?\^')
apertium_re = re.compile(r'[@#~]')
apertium_token_re = re.compile(r'\^.*?\$')

weights_head = '<?xml version="1.0" encoding="UTF-8"?>\n<transfer-weights>\n'
weights_tail = '</transfer-weights>'

beforepunc_re = re.compile(r'([¿("/])(\w)')
afterpunc_re = re.compile(r'(\w)([;:,.!?)"/—])')
quot_re = re.compile("[«»']")
numfix_re = re.compile('([0-9]) ([,.:][0-9])')
beforedash_re = re.compile(r'(\W)-(\w)')
afterdash_re = re.compile(r'(\w)-(\W)')

def normalize(line):
    line = line.lower().replace('--', '—').replace(' - ', ' — ')
    line = quot_re.sub('"', line)
    line = beforedash_re.sub(r'\1— \2', afterdash_re.sub(r'\1 —\2', line))
    line = beforepunc_re.sub(r'\1 \2', afterpunc_re.sub(r'\1 \2', line))
    line = numfix_re.sub(r'\1\2', line)
    return line

def pattern_to_xml(pattern, weight=1.):
    """
    Create XML representation of the pattern for weigths file.
    """
    pattern_line = '      <pattern weight="{}">\n'.format(weight)
    for pattern_item in pattern:
        parts = pattern_item.strip('^$').split('<', maxsplit=1)
        lemma, tags = parts[0], parts[1].strip('>')
        pattern_line += '        <pattern-item lemma="{}" tags="{}"/>\n'.format(lemma, '.'.join(tags.split('><')))
    pattern_line += '      </pattern>\n'
    return pattern_line

def load_rules(pair_data, source, target):
    """
    Load t1x transfer rules file from pair_data folder in source-target direction.
    """
    tixbasename = '{}.{}-{}'.format(os.path.basename(pair_data), source, target)
    tixbasepath = os.path.join(pair_data, tixbasename)
    binbasepath = os.path.join(pair_data, '{}-{}'.format(source, target))
    tixfname = '.'.join((tixbasepath, 't1x'))
    cat_dict, rules, ambiguous_rules, rule_id_map = coverage.prepare(tixfname)
    pattern_FST = coverage.FST(rules)

    return tixbasepath, binbasepath, cat_dict, pattern_FST, ambiguous_rules, rule_id_map

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
    ofname = '{}-tagged.txt'.format(prefix)

    # create partial pipeline
    pipe = pipes.Template()
    pipe.append('apertium -d "{}" {}-{}-tagger'.format(pair_data, source, target), '--')
    pipe.append('apertium-pretransfer', '--')
    
    # tag
    pipe.copy(corpus, ofname)

    print('Done in {:.2f}'.format(clock() - btime))    
    return ofname

def clean_tagged(corpus, prefix):
    """
    Tokenize, lowercase and clean up tagged corpus.
    """
    print('Cleaning up tagged source corpus.')
    btime = clock()

    # make output file name
    ofname = '{}-tagged-clean.txt'.format(prefix)

    with open(corpus, 'r', encoding='utf-8') as ifile, \
         open(ofname, 'w', encoding='utf-8') as ofile:
        for line in ifile:
            ofile.write(inter_re.sub('$ ^', line.replace('"', '').lower()))

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
    """
    print('Looking for ambiguous sentences and translating them.')
    btime = clock()

    # make output file name
    ofname = '{}-ambiguous.txt'.format(prefix)
    #sfname = '{}-sentences.txt'.format(prefix)

    lines_count, total_sents_count, ambig_sents_count, ambig_chunks_count = 0, 0, 0, 0
    botched_coverages = 0
    lbtime = clock()

    with open(corpus, 'r', encoding='utf-8') as ifile, \
         open(ofname, 'w', encoding='utf-8') as ofile: #,\
         #open(sfname, 'w', encoding='utf-8') as sfile:
        for line in ifile:
            lines_count += 1
            if lines_count % 1000 == 0:
                print('\n{} total lines\n{} total sentences\n{} ambiguous sentences\n{} ambiguous chunks\n{} botched coverages\nanother {:.4f} elapsed'.format(lines_count, total_sents_count, ambig_sents_count, ambig_chunks_count, botched_coverages, clock() - lbtime))
                gc.collect()
                lbtime = clock()
            # look at each sentence in line
            for sent_match in sent_re.finditer(line.strip()):
                total_sents_count += 1
                #print(total_sents_count, sent_match.group(0))
                # get coverages
                coverage_list = pattern_FST.get_lrlm(sent_match.group(0), cat_dict)
                if coverage_list == []:
                    botched_coverages += 1
                else:
                    coverage_item = coverage_list[0]
                    # look for ambiguous chunks
                    pattern_list = search_ambiguous(ambiguous_rules, coverage_item)
                    if pattern_list != []:
                        #print(coverage_item)
                        #print()
                        #print(pattern_list)
                        #print()
                        ambig_sents_count += 1
                        # segment the sentence into parts each containing one ambiguous chunk
                        sentence_segments, prev = [], 0
                        for i, rule_group_number, pattern in pattern_list:
                            ambig_chunks_count += 1
                            piece_of_line = '^' + '$ ^'.join(sum([chunk[0] for chunk in coverage_item[prev:i+1]], [])) + '$'
                            sentence_segments.append([rule_group_number, pattern, piece_of_line])
                            prev = i+1

                        if sentence_segments != []:
                            # add up the tail of the sentence
                            if prev <= len(coverage_item):
                                piece_of_line = ' ^' + '$ ^'.join(sum([chunk[0] for chunk in coverage_item[prev:]], [])) + '$'
                                sentence_segments[-1][2] += piece_of_line

                            #print(sentence_segments)
                            #print()

                            # first, translate each segment with default rules
                            for sentence_segment in sentence_segments:
                                sentence_segment.append(translate(sentence_segment[2], tixfname, binfname))

                            # second, translate each segment with all the rules
                            # and make full sentence, where other segments are translated with default rules
                            for j, sentence_segment in enumerate(sentence_segments):
                                translation_list = translate_ambiguous(ambiguous_rules[sentence_segment[0]], 
                                                                       sentence_segment[1], sentence_segment[2],
                                                                       tixfname, binfname, rule_id_map)
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
    print('Done in {:.2f}'.format(clock() - btime))
    return ofname

def translate(sent_line, tixfname, binfname, weightsfname=None):
    """
    Translate sent_line using given weights file.
    """
    # create pipeline
    pipe = pipes.Template()
    pipe.append('lt-proc -b {}'.format('.'.join((binfname, 'autobil.bin'))), '--')
    # use weights file
    if weightsfname is not None:
        pipe.append('apertium-transfer -bw {} {} {}'.format(weightsfname, '.'.join((tixfname, 't1x')), '.'.join((binfname, 't1x.bin'))), '--')
    # do not use weights file
    else:
        pipe.append('apertium-transfer -b {} {}'.format('.'.join((tixfname, 't1x')), '.'.join((binfname, 't1x.bin'))), '--')
    pipe.append('apertium-interchunk {} {}'.format('.'.join((tixfname, 't2x')), '.'.join((binfname, 't2x.bin'))), '--')
    pipe.append('apertium-postchunk {} {}'.format('.'.join((tixfname, 't3x')), '.'.join((binfname, 't3x.bin'))), '--')
    pipe.append('lt-proc -g {}'.format('.'.join((binfname, 'autogen.bin'))), '--')
    pipe.append('apertium-retxt', '--')

    # translate
    pipefile = pipe.open('pipefile', 'w')
    pipefile.write(sent_line)
    pipefile.close()
    return apertium_re.sub('', open('pipefile').read().lower())

def translate_ambiguous(rule_group, pattern, sent_line, tixfname, binfname, rule_id_map):
    """
    Translate sent_line for each rule in rule_group.
    """
    translation_list = []
    pattern = pattern_to_xml(pattern)

    #for each rule
    for focus_rule in rule_group:
        # create weights file favoring that rule
        weights_line = weights_head + '  <rule-group>\n'
        for rule in rule_group:
            weights_line += '    <rule id="{}">\n'.format(rule_id_map[str(rule)])
            if rule == focus_rule:
                weights_line += pattern
            weights_line += '    </rule>\n'
        weights_line += '  </rule-group>\n' + weights_tail
        with open('tmpweights.w1x', 'w', encoding='utf-8') as wfile:
            wfile.write(weights_line)

        # translate using created file
        translation = translate(sent_line, tixfname, binfname, 'tmpweights.w1x')
        translation_list.append((focus_rule, translation))
    return translation_list

def score_sentences(ambig_sentences_fname, model, prefix):
    """
    Score translated sentences.
    """
    print('Scoring ambiguous sentences.')
    btime, chunk_counter, sentence_counter = clock(), 0, 0

    # make output file name
    ofname = '{}-chunk-weights.txt'.format(prefix)

    with open(ambig_sentences_fname, 'r', encoding='utf-8') as ifile, \
         open(ofname, 'w', encoding='utf-8') as ofile:
        reading = True
        while reading:
            try:
                line = ifile.readline()
                group_number, pattern, rulecount = line.rstrip('\n').split('\t')
                weights_list = []
                # score
                total = 0.
                for i in range(int(rulecount)):
                    line = ifile.readline()
                    rule_number, sentence = line.rstrip('\n').split('\t')
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

def make_xml_rules(scores_fname, prefix, rule_map):
    """
    Sum up the weights for each rule-pattern pair,
    add the result to xml weights file.
    """
    print('Summing up the weights and making xml rules.')
    btime = clock()

    # make output file names
    sorted_scores_fname = '{}-chunk-weights-sorted.txt'.format(prefix)
    ofname = '{}-rule-weights.w1x'.format(prefix)

    # create pipe
    pipe = pipes.Template()
    pipe.append('sort $IN > $OUT', 'ff')
    pipe.copy(scores_fname, sorted_scores_fname)

    with open(sorted_scores_fname, 'r', encoding='utf-8') as ifile,\
         open(ofname, 'w', encoding='utf-8') as ofile:
        prev_group_number, prev_rule_number, prev_pattern, weight = ifile.readline().rstrip('\n').split('\t')
        total_pattern_weight = float(weight)
        ofile.write(weights_head)
        ofile.write('  <rule-group>\n    <rule id="{}">\n'.format(rule_map[prev_rule_number]))
        for line in ifile:
            group_number, rule_number, pattern, weight = line.rstrip('\n').split('\t')
            if pattern != prev_pattern:
                # pattern changed, flush previous
                ofile.write(pattern_to_xml(apertium_token_re.findall(prev_pattern), total_pattern_weight))
                total_pattern_weight = 0.
            if group_number != prev_group_number:
                # rule group changed, close previuos, open new
                ofile.write('    </rule>\n  </rule-group>\n  <rule-group>\n    <rule id="{}">\n'.format(rule_map[rule_number]))
            elif rule_number != prev_rule_number:
                # rule changed, close previuos, open new
                ofile.write('    </rule>\n    <rule id="{}">\n'.format(rule_map[rule_number]))
            # add up rule-pattern weights
            total_pattern_weight += float(weight)
            prev_group_number, prev_rule_number, prev_pattern = group_number, rule_number, pattern
        ofile.write('    </rule>\n  </rule-group>\n')
        ofile.write(weights_tail)

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

    # clean up tagged corpus
    #clean_fname = clean_tagged(tagged_fname, prefix)

    # load rules, build rule FST
    tixbasepath, binbasepath, cat_dict, pattern_FST, ambiguous_rules, rule_id_map = \
        load_rules(twlconfig.apertium_pair_data, twlconfig.source, twlconfig.target)

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

    # sum up weigths for rule-pattern and make final xml
    make_xml_rules(scores_fname, prefix, rule_id_map)

    print('Performed in {:.2f}'.format(clock() - tbtime))
