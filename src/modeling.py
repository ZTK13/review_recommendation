""" Modeling module
    ---------------

    Models reviews, users and votes and generates train and test sets.

    Usage:
      $ python -m src.modeling
    on the project root directory.
"""

from math import ceil, log
from datetime import datetime
from copy import deepcopy
from multiprocessing import Pool
from re import match

from numpy import std
from networkx import pagerank
from textblob import TextBlob
from nltk.tokenize import wordpunct_tokenize, sent_tokenize, RegexpTokenizer
from nltk import pos_tag
from nltk.corpus import wordnet
import traceback

from src import sampler
from src import parser
from src.lib.sentiment.sentiwordnet import SimplifiedSentiWordNet


_NUM_THREADS = 8
_SAMPLE_RATIO = 0.5
_TRAIN_FILE = '/var/tmp/luciana/train%d-foreign.csv' % int(_SAMPLE_RATIO * 100)
_TEST_FILE = '/var/tmp/luciana/test%d-foreign.csv' % int(_SAMPLE_RATIO * 100)
_SAMPLE = True


""" Models votes with basic identification data (review id, reviewer id, rater
    id), the vote value and the date of the review (used as an approximation for
    the vote date).

    Args:
      reviews: a dictionary with raw reviews.

    Returns:
      A list with dictionaries representing votes.
"""
def model_votes(reviews):
  votes = []

  for review in reviews.values():
    for rater in review['votes']:
      vote = {}
      vote['review'] = review['id']
      vote['reviewer'] = review['user']
      vote['rater'] = rater
      vote['vote'] = review['votes'][rater]
      vote['date'] = review['date']
      votes.append(vote)

  print '# votes %d' % len(votes)

  return votes


""" Splits votes between train and test sets. They are sorted chronologically
    (by review date) and the first half is used for train and the second,
    for test.

    Args:
      votes: a list with votes dictionaries.

    Returns:
      Two lists of vote dictionaries, the first representing the train set and
    the second, the test set.
"""
def split_votes(votes):
  sorted_reviews = sorted(votes, key=lambda v:
      datetime.strptime(v['date'], '%d.%m.%Y'))
  cut_point = int(ceil(len(votes) / 2.0))
  return votes[:cut_point], votes[cut_point:]


""" Models a review.

    Args:
      raw_review: A dictionary representing a review.

    Returns:
      A dictionary with more keys represented new modeled attributes.
"""
def model_review(raw_review):
  try:
    review = deepcopy(raw_review)
    if get_foreign_ratio(review['text']) >= 0.4:
      return None
    text_feat = get_textual_features(review['text'])
    for feat in text_feat:
        review[feat] = text_feat[feat]
    return review
  except Exception as e:
    traceback.print_exc()
    print()
    raise e


""" Get ratio of foreign (or unidentified) words in a text.

    Args:
      text: a string containing the text.

    Returns:
      A real value with the ratio of foreign words.
"""
def get_foreign_ratio(text):
  text = text.lower()
  word_tokenizer = RegexpTokenizer(r'\w+')
  words = word_tokenizer.tokenize(text)
  fw = [w for w in words if match('[a-z]+', w) and wordnet.synsets(w) == []]
  if len(words) > 0:  
    return float(len(fw)) / len(words)
  else:
    return 0


""" Reports different features derived from text, related to length, syntax,
    lexicon and sentiment statistics.

    Args:
        text: the text to derive the features from.

    Returns:
        A dictionary from feature names to feature value. Refer to
    "get_text_length_stats", "get_pos_stats" and "get_sent_stats" for complete
    list of feature names.
"""
def get_textual_features(text):
    text = text.replace(r'  \d\d\d\d;','#').replace(r'&#\d\d\d\d;','#') \
        .replace('quot;', '#').replace('lt;', '#').replace('gt;', '#')
        # it is considered that unicode are commonly symbols.
    lower_text = text.lower()

    features = {}
    length_feat = get_text_length_stats(text)
    for feat in length_feat:
        features[feat] = length_feat[feat]

    pos_feat = get_pos_stats(lower_text)
    for feat in pos_feat:
        features[feat] = pos_feat[feat]

    sent_feat = get_sent_stats(lower_text)
    for feat in sent_feat:
      features[feat] = sent_feat[feat]

    return features


""" Gets length statistics of the text: number of chars, number of tokens,
    number of words, number of sentences, ratio of unique words, average number
    of tokens by sentence and ratio of capitalized sentences.

    Args:
        text: the text to calculate statistics from.

    Returns:
        A dictionary indexed by keys "num_chars", "num_tokens", "num_words",
    "num_sents", "uni_ratio", "avg_sent" and "cap_sent", and containing as
    values the corresponding statistic value.
"""
def get_text_length_stats(text):
    features = {}

    word_tokenizer = RegexpTokenizer(r'\w+')

    tokens = wordpunct_tokenize(text)
    words = word_tokenizer.tokenize(text)
    sents = sent_tokenize(text)
    capsents = [s for s in sents if match('[A-Z]', s[0])] 

    features['num_chars'] = len(text)
    features['num_tokens'] = len(tokens)
    features['num_words'] = len(words)
    features['num_sents'] = len(sents)
    features['uni_ratio'] = float(len(set(words))) / len(words) if len(words) \
        else 0.0
    features['avg_sent'] = float(features['num_tokens']) / \
        features['num_sents'] if features['num_sents'] else 0.0
    features['cap_sent'] = float(len(capsents)) / len(sents) if len(sents) \
        else 0.0

    return features


""" Gets ratios of some POS tags: noun, adjective, adverb, comparatives
    (adjective or adverb), foreign words, symbols, numbers and punctuations.

    Args:
        text: the text to calculate POS tags ratios from.

    Returns:
        A dictionary indexed by keys "noun_ratio", "adj_ratio", "adv_ratio",
    "verb_ratio", "comp_ratio", "fw_ratio", "sym_ratio", "num_ratio" and
    "punct_ratio", and containing as values the ratios of the corresponding
    tag accross all words of the text.
"""
def get_pos_stats(text):
    features = {'noun_ratio': 0.0, 'adj_ratio': 0.0, 'adv_ratio': 0.0,
        'verb_ratio': 0.0, 'comp_ratio': 0.0, 'fw_ratio': 0.0,
        'sym_ratio': 0.0, 'num_ratio': 0.0, 'punct_ratio': 0.0}

    tokens = wordpunct_tokenize(text)
    tags = pos_tag(tokens)

    for _, tag in tags:
      if tag == 'FW' or (match('[a-z]+', tag) and wordnet.synsets(tag) == []):
        features['fw_ratio'] += 1.0 # order is important
      elif tag.startswith('NN'):
        features['noun_ratio'] += 1.0
      elif tag.startswith('JJ'):
        features['adj_ratio'] += 1.0
      elif tag.startswith('RB'):
        features['adv_ratio'] += 1.0
      elif tag.startswith('VB'):
        features['verb_ratio'] += 1.0
      elif tag == 'JJR' or tag == 'RBR':
        features['comp_ratio'] += 1.0
      elif tag == 'CD':
        features['num_ratio'] += 1.0
      elif tag == 'SYM' or tag == ':' or tag == '.':
        features['sym_ratio'] += 1.0
      elif tag == 'SYM' or tag == ':' or tag == '.' and tag in PUNCTUATION:
        features['punct_ratio'] += 1.0

    for tag in ['noun_ratio', 'adj_ratio', 'adv_ratio', 'verb_ratio', 'comp_ratio',
            'fw_ratio', 'sym_ratio', 'num_ratio', 'punct_ratio']:
        features[tag] = features[tag] / len(tokens) if len(tokens) else 0.0

    return features


""" Gets positive and negative ratio of sentences and words. Sentence ratio
    has a better context for deriving meaning and, consequently, sentiment. Word
    related ratio is calculated using the first meaning of the identified tag.

    ****** BOTH ARE GOING TO BE EVALUATED IN ORDER TO CHOOSE THE ONE WITH BEST
    PERFORMANCE. ***********

    Args:
      text: the text to analyze polarity scores.

    Returns:
      Two real values, pos_ratio and neg_ratio, with, respectively the ratio of
    positive sentences and the ratio of negative sentences.
"""
def get_sent_stats(text):
  features = {}
  tblob = TextBlob(text)

  pos = neg = total = 0.0
  for s in tblob.sentences:
    if s.sentiment.polarity > 0:
      pos += 1.0
    elif s.sentiment.polarity < 0:
      neg += 1.0
    total += 1.0
  features['pos_sent'] = pos / total if total else 0.0
  features['neg_sent'] = neg / total if total else 0.0

  swn = SimplifiedSentiWordNet()
  features['pos_ratio'] = 0
  features['neg_ratio'] = 0
  for word, tag in tblob.tags:
    if tag.startswith('NN'):
      tag = 'n'
    elif tag.startswith('JJ'):
      tag = 'a'
    elif tag.startswith('VB'):
      tag = 'v'
    elif tag.startswith('RB'):
      tag = 'r'
    else:
      continue
    scores = swn.scores(word, tag)
    if scores:
      if scores['pos_score'] > scores['neg_score']:
        features['pos_ratio'] += 1
      elif scores['neg_score'] > scores['pos_score']:
        features['neg_ratio'] += 1
  features['pos_ratio'] = features['pos_ratio'] / float(len(tblob.words)) if \
      len(tblob.words) else 0.0
  features['neg_ratio'] = features['neg_ratio'] / float(len(tblob.words)) if \
      len(tblob.words) else 0.0
  
  return features


""" Groups review by product.

    Args:
      reviews: a dictionary of reviews.

    Returns:
      A dictionary indexed firstly by product name and secondly by review ids,
    containing review dictionaries as second order values.
"""
def group_reviews_by_product(reviews):
  grouped_reviews = {}

  for review in reviews.values():
    if review['product'] not in grouped_reviews:
      grouped_reviews[review['product']] = []
    grouped_reviews[review['product']].append(review)

  return grouped_reviews


""" Calculates KL divergence between unigram models of review's text and all
    reviews' texts from the corresponding product.

    Args:
      reviews: a dictionary of reviews.

    Returns:
      None. The KL divergence value is create in each review dictionary under
    the key 'kl'.
"""
def calculate_kl_divergence(reviews):
  grouped_reviews = group_reviews_by_product(reviews)

  avg_unigram = {}
  total_words = 0
  for product in grouped_reviews:
    for review in grouped_reviews[product]:
      review['unigram'], num_words = get_unigram_model(review['text'])
      for word in review['unigram']:
        if word not in avg_unigram:
          avg_unigram[word] = 0
        avg_unigram[word] += review['unigram'][word]
      total_words += num_words
    for word in avg_unigram:
      avg_unigram[word] = avg_unigram[word] / total_words if total_words else 0
    for review in grouped_reviews[product]:
      review['kl'] = 0
      for word in review['unigram']:
        if not avg_unigram[word]:
          continue
        review['kl'] += review['unigram'][word] * log(review['unigram'][word] /
            avg_unigram[word])
      review.pop('unigram', None)


""" Gets an unigram model for a given text.

    Args:
      text: the text to get the model of.

    Returns:
      A dictionary with the counts of words and the number of words.

    Obs.: The unigram model is not retrieved ready, with counts normalized to
    ratios, because the intermediate representations makes it easier to
    aggregate unigram models for all reviews of a product.
"""
def get_unigram_model(text):
  unigram = {}
  text_blob = TextBlob(text)

  for word in text_blob.words:
    if word.decode() not in unigram:
      unigram[word.decode()] = 0.0
    unigram[word.decode()] += 1.0

  for word in unigram:
    unigram[word] = unigram[word] / len(text_blob.words) if \
        len(text_blob.words) else 0

  return unigram, len(text_blob.words)


""" Groups votes by review.

    Args:
      votes: a list of votes' dictionaries.

    Returns:
      A dictionary indexed by review ids and containing a list of votes as
    values.
"""
def group_votes_by_review(votes):
  grouped_votes = {}

  for vote in votes:
    if vote['review'] not in grouped_votes:
      grouped_votes[vote['review']] = []
    grouped_votes[vote['review']].append(vote)

  return grouped_votes


""" Initializes user features.

    Args:
      None.

    Returns:
      A dictionary with initialized values representing a user.
"""
def create_user(user_id):
  user = {}
  user['id'] = user_id
  user['num_reviews'] = 0
  user['num_votes_rec'] = 0
  user['num_votes_giv'] = 0
  user['avg_rating'] = 0
  user['sd_rating'] = []
  user['sd_help_rec'] = []
  user['sd_help_giv'] = []
  user['avg_rel_rating'] = 0
  user['avg_help_rec'] = 0
  user['avg_help_giv'] = 0
  user['avg_rel_help_giv'] = 0
  user['num_trustees'] = 0
  user['num_trustors'] = 0
  return user


""" Creates empty dummy user for cold start.

    Args:
      None.

    Returns:
      A dictionary with initialized values representing a user.
"""
def get_empty_user():
  user = {}
  user['num_reviews'] = 0
  user['num_votes_rec'] = 0
  user['num_votes_giv'] = 0
  user['avg_rating'] = 0
  user['sd_rating'] = 0
  user['sd_help_rec'] = 0
  user['sd_help_giv'] = 0
  user['avg_rel_rating'] = 0
  user['avg_help_rec'] = 0
  user['avg_help_giv'] = 0
  user['avg_rel_help_giv'] = 0
  user['num_trustees'] = 0
  user['num_trustors'] = 0
  return user


""" Adds user rating, updating related features.

    Args:
      user: the user dictionary whose fields must be updated.
      rating: the rating value.

    Returns:
      None. Changes are made in place.
"""
def add_user_rating(user, rating):
  user['num_reviews'] += 1
  user['avg_rating'] += float(rating)
  user['sd_rating'].append(float(rating))


""" Adds user vote, updating related features.

    Args:
      reviewer: the user dictionary of the reviewer.
      rater: the user dictionary of the rater.
      vote: the value of the vote.
      avg_help: the average helpfulness of the review being voted.

    Returns:
      None. Changes are made in place.
"""
def add_user_vote(reviewer, rater, vote, avg_help):
  reviewer['num_votes_rec'] += 1
  reviewer['avg_help_rec'] += int(vote)
  reviewer['sd_help_rec'].append(vote)

  rater['num_votes_giv'] += 1
  rater['avg_help_giv'] += int(vote)
  rater['avg_rel_help_giv'] +=  float(vote) - avg_help
  rater['sd_help_giv'].append(float(vote))


""" Finalizes user features, normalizing or aggregating features.

    Args:
      user: a user dictionary.

    Returns:
      None. Changes are made in place.
"""
def finalize_user_features(users, trusts):
  prank = pagerank(trusts)
  remove_users = set()
  for user in users:
    if users[user]['num_reviews'] == 0 or users[user]['num_votes_rec'] == 0 \
        or users[user]['num_votes_giv'] == 0:
      remove_users.add(user)
      continue
    users[user]['avg_rating'] /= float(users[user]['num_reviews'])
    users[user]['avg_rel_rating'] /= float(users[user]['num_reviews'])
    users[user]['sd_rating'] = std(users[user]['sd_rating'], ddof=1)
    users[user]['avg_help_rec'] /= float(users[user]['num_votes_rec'])
    users[user]['sd_help_rec'] = std(users[user]['sd_help_rec'], ddof=1)
    users[user]['avg_help_giv'] /= float(users[user]['num_votes_giv'])
    users[user]['avg_rel_help_giv'] /= float(users[user]['num_votes_giv'])
    users[user]['sd_help_giv'] = std(users[user]['sd_help_giv'], ddof=1)
    users[user]['pagerank'] = prank[user] if user in prank else 0.0
  for user in remove_users:
    users.pop(user, None)


""" Includes trust relation under trustor and trustee statistics.

    Args:
      trustor: the user dictionary of the person who trusts in the relation.
      trustee: the user dictionary of the person who is trusted in the relation.

    Returns:
      None. Changes are made in place.
"""
def account_trust_relation(trustor, trustee):
  if trustor:
    trustor['num_trustees'] += 1
  if trustee:
    trustee['num_trustors'] += 1


""" Models users, aggregating information from reviews and trust relations.

    Args:
      reviews: a dictionary with modeled reviews.
      train: a list of votes used as train.
      trusts: a networkx DiGraph object.

    Returns:
      A dictionary of users indexed by user ids.
"""
def model_users(reviews, train, trusts):
  users = {}

  grouped_train = group_votes_by_review(train)
  print '# reviews in grouped_train: %d' % len(grouped_train)
  for review_id in grouped_train:
    review = reviews[review_id]
    if review['user'] not in users:
      print 'new_user'
      rev_dict = create_user(review['user'])
      users[review['user']] = rev_dict
    add_user_rating(users[review['user']], review['rating'])
    avg_help = float(sum([v['vote'] for v in grouped_train[review_id]])) / \
        len(grouped_train[review_id])
    for vote in grouped_train[review_id]:
      if vote['rater'] not in users:
        print 'new_user'
        rat_dict = create_user(vote['rater'])
        users[vote['rater']] = rat_dict
      add_user_vote(users[review['user']], users[vote['rater']], vote['vote'],
          avg_help)
  print len(users)
  print users.keys()
  for trustor in trusts:
    for trustee in trusts[trustor]:
      account_trust_relation(users[trustor] if trustor in users else None,
          users[trustee] if trustee in users else None)
  finalize_user_features(users, trusts)
  print len(users)
  print users.keys()

  return users


""" Models reviews in parallel using _NUM_THREADS threads.

    Args:
      sample_raw_reviews: (optional) The sample set of reviews to be modeled.

    Returns:
      A dictionary of reviews indexed by reviews' ids.
"""
def model_reviews_parallel(sample_raw_reviews=None):
  raw_reviews = sample_raw_reviews if sample_raw_reviews else [r for r in
      parser.parse_reviews()]

  pool = Pool(processes=_NUM_THREADS)
  result = pool.imap_unordered(model_review, iter(raw_reviews), len(raw_reviews)
      / _NUM_THREADS + 1)
  pool.close()
  print 'Waiting for processes'
  pool.join()
  print 'Processes have finished'

  print 'Creating dict'
  result = [review for review in result if review]
  reviews = {review['id']:review for review in result}

  print 'Lenght of dictionary %d' % len(reviews)

  print 'Calculating KL divergence'
  calculate_kl_divergence(reviews)
      # cannot be parallelized without concurrence control
      # Correction: it is possible dividing by product

  return reviews


""" Models reviews, users and votes in order to generate features from
    train and test sets. Aggregated statistics from test set includes reviews
    from both train and test set.

    Args:
      None.

    Returns:
      None. Calls output_model which outputs to files.
"""
def model():
  print 'Getting trust'
  trusts = parser.parse_trusts()

  print 'Modeling reviews'
  if _SAMPLE:
    sel_reviews = sampler.sample_reviews(_SAMPLE_RATIO)
    reviews = model_reviews_parallel(sel_reviews)
  else:
    reviews = model_reviews_parallel()

  print 'Model votes'
  votes = model_votes(reviews)

  print 'Split train and test'
  train, test = split_votes(votes)

  print 'train: %d, test: %d' % (len(train), len(test))

  print 'Modeling users'
  users = model_users(reviews, train, trusts)

  print 'users: %d' % len(users)

  print 'Outputting'
  output_model(train, test, reviews, users, trusts)


""" Outputs feature model.

    Args:
      train: a list of votes belonging to train set.
      test: the list of votes belonging to test set.
      reviews: a dictionary of reviews.
      users: a dictionary of users with aggregated information from train
    set.
      trusts: a networkx DiGraph object.

    Returns:
      None. The output is inserted in _TRAIN_FILE and _TEST_FILE.
"""
def output_model(train, test, reviews, users, trusts):
  train_f = open(_TRAIN_FILE, 'w')
  test_f = open(_TEST_FILE, 'w')

  for out in [train_f, test_f]:
    print >> out, ('review_id,reviewer_id,rater_id,rating,'
        'num_chars,num_tokens,num_words,num_sents,unique_ratio,avg_sent,'
        'cap_ratio,noun_ratio,adj_ratio,adv_ratio,verb_ratio,comp_ratio,'
        'fw_ratio,sym_ratio,num_ratio,punct_ratio,'
        'pos_sent,neg_sent,pos_ratio,neg_ratio,kl_div,'
        'r_num_reviews,r_avg_rating,r_avg_help_rec,'
        'r_num_trustors,r_num_trustees,r_avg_help_giv,r_avg_rel_help_giv,'
        'r_sd_rating,r_sd_help_rec,r_sd_help_giv,r_pagerank,'
        'u_num_reviews,u_avg_rating,u_avg_help_rec,'
        'u_num_trustors,u_num_trustees,u_avg_help_giv,u_avg_rel_help_giv,'
        'u_sd_rating,u_sd_help_rec,u_sd_help_giv,u_pagerank,trust,truth')

  for partition, out in [(train, train_f), (test, test_f)]:
    for vote in partition:
      r = reviews[vote['review']]
      if r['user'] not in users or vote['rater'] not in users:
        continue
      rvr = users[r['user']]
      rtr = users[vote['rater']]
      trust = 1 if vote['rater'] in trusts and r['user'] in \
          trusts[vote['rater']] else 0
      print >> out, ('%s,%s,%s,%d,'
          '%d,%d,%d,%d,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,' 
          '%d,%f,%f,%d,%d,%f,%f,%f,%f,%f,%f,'
          '%d,%f,%f,%d,%d,%f,%f,%f,%f,%f,%f,'
          '%d,%d') % (
          r['id'], r['user'], vote['rater'], r['rating'],
          r['num_chars'],r['num_tokens'],r['num_words'],r['num_sents'],
          r['uni_ratio'],r['avg_sent'],
          r['cap_sent'],
          r['noun_ratio'],r['adj_ratio'],r['adv_ratio'],r['verb_ratio'],
          r['comp_ratio'],r['fw_ratio'],r['sym_ratio'],r['num_ratio'],
          r['punct_ratio'],
          r['pos_sent'],r['neg_sent'],r['pos_ratio'],r['neg_ratio'],r['kl'],
          rvr['num_reviews'],rvr['avg_rating'],
          rvr['avg_help_rec'],rvr['num_trustors'],rvr['num_trustees'],
          rvr['avg_help_giv'],rvr['avg_rel_help_giv'],rvr['sd_rating'],
          rvr['sd_help_rec'],rvr['sd_help_giv'],rvr['pagerank'],
          rtr['num_reviews'],rtr['avg_rating'],
          rtr['avg_help_rec'],rtr['num_trustors'],rtr['num_trustees'],
          rtr['avg_help_giv'],rtr['avg_rel_help_giv'],rtr['sd_rating'],
          rtr['sd_help_rec'],rtr['sd_help_giv'],rtr['pagerank'],
          trust, vote['vote'])

  train_f.close()
  test_f.close()


if __name__ == '__main__':
  model()
