# learning mode, must be one of the following:
# "mono": learn weights from monolingual corpus using pretrained language module
# "parallel": learn weights from parallel corpus (no language model required)
mode = "mono"
#mode = "parallel"

# full path to source language corpus from which to learn the rules
source_language_corpus = "/home/nm/source/apertium/weighted-transfer/apertium-weights-learner/data/2007-en-100000.txt"

# full path to target language corpus (only for parallel mode)
#target_language_corpus = "/home/nm/source/apertium/weighted-transfer/apertium-weights-learner/data/nc-v7.es-en.es.100.txt"

# name of apertium language pair (not translation direction)
apertium_pair_name = "en-es"

# full path to apertium language pair data folder
apertium_pair_data = "/home/nm/source/apertium/weighted-transfer/apertium-en-es"

# translation direction
source = "en"
target = "es"

# full path to kenlm language model (only for mono mode)
# may be either arpa (text format) or mmap (binary) 
# but mmap is strongly preferred as it loads and scores faster
language_model = "/media/nm/storage/es-news-tokenized.mmap"

# full path to a folder where to store intermediate data and results
data_folder = "/home/nm/source/apertium/weighted-transfer/apertium-weights-learner/data/"

# optional common prefix for all intermediate and resulting files
#fname_common_prefix = "en-es-newscommentary"
