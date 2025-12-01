

import pickle
import pandas as pd
import numpy as np
import string

import nltk
# Comment out these statements if your packages are already up-to-date!
nltk.download('stopwords')
nltk.download('punkt')
nltk.download('averaged_perceptron_tagger')
nltk.download('wordnet')
# ------------------------ #
from nltk.stem import WordNetLemmatizer
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

from keras.models import Model
from keras.layers import Dense, Input, Dropout, LSTM, Activation
##from tensorflow.keras.layers.embeddings import Embedding
from tensorflow.keras.layers import Embedding
from keras.preprocessing import sequence
from keras.initializers import glorot_uniform

lemmatizer = WordNetLemmatizer()
stop_words = set(stopwords.words('english'))
stop_words.update(list(string.punctuation))
# Preserve pronouns and negations which can be important for threats/context
important_keep = {
    'i','you','he','she','they','we','us','him','her','them',
    'his','hers','your','yours','my','me','mine','our','ours',
    'not','no','never',"n't"
}
# Remove important words from the stopword set so they aren't dropped
stop_words = stop_words.difference(important_keep)

def init():
    global word_to_index, max_len
    #word_to_index, index_to_word, word_to_vec_map = read_glove_vecs('glove.6B.50d.txt')
    filename = 'src/word_to_index.pkl'
    word_to_index =  pickle.load(open(filename, 'rb')) 
    max_len = 30
    print(len(word_to_index))
    return word_to_index, max_len

def clean_text(review) :
    global max_len
    if not review or not isinstance(review, str):
        return ""
    try:
        words = word_tokenize(review)
        output_words = []
        for word in words :
            word_lower = word.lower()
            if word_lower not in stop_words :
                # Simple lemmatization without POS tagging to avoid wordnet corpus issues
                clean_word = lemmatizer.lemmatize(word_lower)
                output_words.append(clean_word)
        max_len = max(max_len, len(output_words))
        return " ".join(output_words)
    except Exception as e:
        print(f'Error in clean_text: {e}')
        # Fallback: return lowercased words without lemmatization if error occurs
        try:
            words = word_tokenize(review)
            return " ".join([w.lower() for w in words if w.lower() not in stop_words])
        except:
            return review.lower()
    return " ".join(output_words)

def read_glove_vecs(glove_file):
    with open(glove_file, 'r', encoding="utf8") as file:
        word_to_vec_map = {}
        word_to_index = {}
        index_to_word = {}
        index = 0
        for line in file:
            line = line.strip().split()
            curr_word = line[0]
            word_to_index[curr_word] = index
            index_to_word[index] = curr_word
            word_to_vec_map[curr_word] = np.array(line[1:], dtype=np.float64)
            index += 1
    return word_to_index, index_to_word, word_to_vec_map

def sentences_to_indices(X, word_to_index, max_len):
    m = len(X)
    X_indices = np.zeros((m, max_len))
    for i in range(m):
        sentence_words = [w.lower() for w in X[i].split()]
        j = 0
        for word in sentence_words:
            if word in word_to_index:
                X_indices[i, j] = word_to_index[word]
            j += 1
    return X_indices
