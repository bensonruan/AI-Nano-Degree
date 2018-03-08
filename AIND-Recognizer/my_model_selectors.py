import math
import statistics
import warnings

import numpy as np
from hmmlearn.hmm import GaussianHMM
from sklearn.model_selection import KFold
from asl_utils import combine_sequences


class ModelSelector(object):
    '''
    base class for model selection (strategy design pattern)
    '''

    def __init__(self, all_word_sequences: dict, all_word_Xlengths: dict, this_word: str,
                 n_constant=3,
                 min_n_components=2, max_n_components=10,
                 random_state=14, verbose=False):
        self.words = all_word_sequences
        self.hwords = all_word_Xlengths
        self.sequences = all_word_sequences[this_word]
        self.X, self.lengths = all_word_Xlengths[this_word]
        self.this_word = this_word
        self.n_constant = n_constant
        self.min_n_components = min_n_components
        self.max_n_components = max_n_components
        self.random_state = random_state
        self.verbose = verbose

    def select(self):
        raise NotImplementedError

    def base_model(self, num_states):
        # with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        warnings.filterwarnings("ignore", category=RuntimeWarning)
        try:
            hmm_model = GaussianHMM(n_components=num_states, covariance_type="diag", n_iter=1000,
                                    random_state=self.random_state, verbose=False).fit(self.X, self.lengths)
            if self.verbose:
                print("model created for {} with {} states".format(self.this_word, num_states))
            return hmm_model
        except:
            if self.verbose:
                print("failure on {} with {} states".format(self.this_word, num_states))
            return None


class SelectorConstant(ModelSelector):
    """ select the model with value self.n_constant

    """

    def select(self):
        """ select based on n_constant value

        :return: GaussianHMM object
        """
        best_num_components = self.n_constant
        return self.base_model(best_num_components)


class SelectorBIC(ModelSelector):
    """ select the model with the lowest Bayesian Information Criterion(BIC) score

    http://www2.imm.dtu.dk/courses/02433/doc/ch6_slides.pdf
    Bayesian information criteria: BIC = -2 * logL + p * logN
    """

    def select(self):
        """ select the best model for self.this_word based on
        BIC score for n between self.min_n_components and self.max_n_components

        :return: GaussianHMM object
        """
        warnings.filterwarnings("ignore", category=DeprecationWarning)

        # implement model selection based on BIC scores
        best_score = float("inf")
        best_model = None
        for n in range(self.min_n_components, self.max_n_components + 1):
            try:
                model = self.base_model(n)
                p = n * (n-1) + 2 * len(self.X[0]) * n
                logL = model.score(self.X, self.lengths)
                logN = np.log(len(self.X))
                score = -2 * logL + p * logN
                if score < best_score:
                    best_score = score
                    best_model = model
            except:
                continue
        return best_model


class SelectorDIC(ModelSelector):
    ''' select best model based on Discriminative Information Criterion

    Biem, Alain. "A model selection criterion for classification: Application to hmm topology optimization."
    Document Analysis and Recognition, 2003. Proceedings. Seventh International Conference on. IEEE, 2003.
    http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.58.6208&rep=rep1&type=pdf
    https://pdfs.semanticscholar.org/ed3d/7c4a5f607201f3848d4c02dd9ba17c791fc2.pdf
    DIC = log(P(X(i)) - 1/(M-1)SUM(log(P(X(all but i))
    '''

    def select(self):
        warnings.filterwarnings("ignore", category=DeprecationWarning)

        # implement model selection based on DIC scores
        best_score = -float("inf")
        best_n = None
        for n in range(self.min_n_components, self.max_n_components + 1):
            try:
                logPXi = self.base_model(n).score(self.X, self.lengths)

                sumLogPX = 0.
                words = list(self.words.keys())
                M = len(words)
                words.remove(self.this_word)

                for word in words:
                    try:
                        all_but_i = ModelSelector(self.words, self.hwords, word, self.n_constant, self.min_n_components, self.max_n_components, self.random_state, self.verbose)
                        sumLogPX += all_but_i.base_model(n).score(all_but_i.X, all_but_i.lengths)
                    except:
                        M = M - 1

                DIC = logPXi - sumLogPX / (M - 1)

                if best_score is None or best_score < DIC:
                  best_score, best_n = DIC, n
            except:
                pass

        if best_n is None:
            return self.base_model(self.n_constant)
        else:
            return self.base_model(best_n)

class SelectorCV(ModelSelector):
    ''' select best model based on average log Likelihood of cross-validation folds

    '''

    def select(self):
        warnings.filterwarnings("ignore", category=DeprecationWarning)

        # implement model selection using CV
        best_score = -float("inf")
        best_num_state = 1
        best_model = None

        for n in range(self.min_n_components, self.max_n_components + 1):
            i = 0
            total_score = 0
            word_sequences = self.sequences
            try:
                kfold_idx = KFold(n_splits=min(3, len(word_sequences)))
            except:
                return None
            try:
                for cv_train_idx, cv_test_idx in kfold_idx.split(word_sequences):
                    cv_train_x, cv_train_length = combine_sequences(cv_train_idx, word_sequences)
                    cv_test_x, cv_test_length = combine_sequences(cv_test_idx, word_sequences)
                    model = GaussianHMM(n_components=n, covariance_type="diag", n_iter=1000,
                                        random_state=self.random_state, verbose=False).fit(cv_train_x, cv_train_length)
                    total_score = total_score + model.score(cv_test_x, cv_test_length)
                    i = i + 1
                if total_score / i > best_score:
                    best_score = total_score / i
                    best_num_state = n
            except:
                continue
        best_model = self.base_model(best_num_state)
        return best_model
