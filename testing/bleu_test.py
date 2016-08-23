#! /usr/bin/python3

import re, sys
from nltk import bleu_score

word_re = re.compile('\w+')

def prepare_corpus(fname, ref=False):
    text = []
    with open(fname, 'r', encoding='utf-8') as ifile:
        for line in ifile:
            if ref:
                text.append([word_re.findall(line)])
            else:
                text.append(word_re.findall(line))
    return text

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: ./bleu_test.py REFERENCE UNWEIGHTED_TRANSLATION WEIGHTED_TRANSLATION")
        sys.exit(1)

    ref_corpus = prepare_corpus(sys.argv[1], ref=True)
    unw_corpus = prepare_corpus(sys.argv[2])
    wei_corpus = prepare_corpus(sys.argv[3])

    print("\nCorpus BLEU")

    print("Unweighted:", bleu_score.corpus_bleu(ref_corpus, unw_corpus))
    print("Weighted:", bleu_score.corpus_bleu(ref_corpus, wei_corpus))

    print("\nAverage sentence BLEU")

    print("Unweighted:", sum(bleu_score.sentence_bleu(ref, hyp) for ref, hyp in zip(ref_corpus, unw_corpus) if ref != [[]] and hyp != []) / len(ref_corpus))
    print("Weighted:", sum(bleu_score.sentence_bleu(ref, hyp) for ref, hyp in zip(ref_corpus, wei_corpus) if ref != [[]] and hyp != []) / len(ref_corpus))
