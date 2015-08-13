""" Sampler module
    --------------

    Sample reviews randomly.

    This module is used by other modules and should not be directly called.
"""

from random import sample
from math import ceil

from src.parsing import parser


""" Samples reviews.

    Args:
      sample_ratio: the ratio amount of reviews that should be included in the
    sample.

    Returns:
      A list of sampled raw reviews.
"""
def sample_reviews(sample_ratio):
  reviews = [r for r in parser.parse_reviews()]

  sel_reviews = sample(reviews, int(ceil(len(reviews) * sample_ratio)))

  return sel_reviews
