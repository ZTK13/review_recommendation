""" Scaling Module
    --------------

    Fits a scaler to training data and applies to train and test. There are two
    options of scalers: (1) a standard scaler, obtaining zero mean and unit
    variance for features; and (2) a minmax scaler, which maps features ranges
    to interval [0, 1].

    Usage:
      Used only as a module, not directly callable.
"""


from sklearn.preprocessing import StandardScaler, MinMaxScaler
from numpy import array, hstack, hsplit

def group_by_qid(data, qid):
  """ Groups instances by query id (user).
      
      Args:
        data: 2-D array with instances in lines and features in columns.
        qid: list of query ids associated to each instance, in the same order.

      Returns:
        A dictionary indexed by query id and containing a list of instances
      arrays associated with it.
  """
  grouped = {}
  for i in xrange(data.shape[0]):
    if qid[i] not in grouped:
      grouped[qid[i]] = []
    grouped[qid[i]].append(data[i,:])
  return grouped


def fit_scaler(scale_type, data):
  """ Fits a scaler to a data.

      Args:
        scale_type: indicates the type of scale to adopt. It can be 'standard' to 
          scale with zero mean and unit standard deviation, or 'minmax' for range
          between 0 and 1.
        data: list of arrays with instances to be scaled.

      Returns:
        A scaler that fits the data.
  """
  if scale_type == 'standard':
    return StandardScaler(copy=False).fit(data)
  if scale_type == 'minmax':
    return MinMaxScaler(copy=False).fit(data)


def fit_scaler_by_query(scale_type, data, qid, qid_dep_size):
  """ Fits a scaler to data.

      Args:
        scale_type: indicates the type of scale to adopt. It can be 'standard' to 
          scale with zero mean and unit standard deviation, or 'minmax' for range
          between 0 and 1.
        data: list of arrays with instances to be scaled.

      Returns:
        A scaler that fits the data.
  """
  data = array(data)
  dim = data.shape[1]
  q_undep, q_dep = hsplit(data, [dim-qid_dep_size])
  q_scalers = {}
  if scale_type == 'standard':
    overall_scaler = StandardScaler(copy=False).fit(q_undep)
    for q in qid_grouped: 
      q_scalers[q] = StandardScaler(copy=False).fit(qid_grouped[q])
  if scale_type == 'minmax':
    overall_scaler = MinMaxScaler(copy=False).fit(q_undep)
    qid_grouped = group_by_qid(q_dep, qid)
    for q in qid_grouped: 
      if len(qid_grouped[q]) > 10:
        q_scalers[q] = MinMaxScaler(copy=False).fit(qid_grouped[q])
    q_scalers['all'] = MinMaxScaler(copy=False).fit(q_dep)
  return overall_scaler, q_scalers


def scale_features(scaler, data, qid=None, qid_dep_size=None):
  """ Scales features from train and test, after fitting scaler on train.

      Observation:
      - The scaler is fit only using training set and, then, applied to both
      train and test.

      Args:
        scale_type: string with scale type, either 'standard' of 'minmax'.
        train: list of instances of the train.
        test: list of instances of the test.

      Returns:
        A pair with scaled train and test sets. 
  """
  data = array(data)
  if qid is None:
    data = scaler.transform(data)
  else:
    dim = data.shape[1]
    overall_scaler, q_scalers = scaler
    q_undep, q_dep = hsplit(data, [dim-qid_dep_size])
    q_undep = overall_scaler.transform(q_undep)
    for i in xrange(q_dep.shape[0]):
      if qid[i] in q_scalers:
        q_dep[i] = q_scalers[qid[i]].transform([q_dep[i]]) # assignments necessary?
      else:
        q_dep[i] = q_scalers['all'].transform([q_dep[i]])
    data = hstack((q_undep, q_dep))
  return data 

