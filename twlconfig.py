# full path to source corpus from which to learn the rules
#source_corpus = "/home/nm/source/apertium/weighted-transfer/apertium-weights-learner/data/2007-en-100.txt"
source_corpus = "/home/nm/source/apertium/weighted-transfer/apertium-weights-learner/data/new-software-sample.txt"

# name of apertium language pair (not translation direction)
apertium_pair_name = "en-es"

# full path to apertium language pair data folder
apertium_pair_data = "/home/nm/source/apertium/weighted-transfer/apertium-en-es"

# translation direction
source = "en"
target = "es"

# full path to kenlm language model
# may be either arpa (text format) or mmap (binary) 
# but mmap is strongly preferred as it loads and scores faster
language_model = "/media/nm/storage/es-news-tokenized.mmap"

# full path to a folder where to store intermediate data and results
data_folder = "/home/nm/source/apertium/weighted-transfer/apertium-weights-learner/data/"
