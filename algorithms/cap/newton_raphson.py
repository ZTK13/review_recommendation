""" Netwon-Raphson Module
    ---------------------

    Computes root of a function using Newton-Raphson method. This method is used
    in the E-step to compute the parameters of interaction variables regression,
    since it is not linear due to sigmoid function. This is equivalent to
    finding the root of the derivative of the squared error of the regression,
    what is done here.

    Not directly callable.
"""

from numpy import  allclose, zeros
from numpy.linalg import pinv

from algorithms.cap.const import NR_ITER, NR_TOL, NR_STEP


def newton_raphson(fun, der, variable_group, theta_0, n_iter=NR_ITER, eps=NR_TOL, 
    step=NR_STEP):
  """ Applies Newton-Raphson's Method. This method finds an approximation for a 
      root of a function numerically by continuously updating acording to the
      derivative and the function at the current value of the variable. 
      
      Obs: In our case, it finds the optimal value of a function by finding the
      root of its derivative, thus it uses the first and the second order
      derivative.

      Args:
        fun: function which evaluates over theta to calculate the root of.
        der: function which evaluates over theta and represents the derivative.
        theta_0: value of initial theta.
        n_iter: number of iterations to perform.
        eps: tolerance for difference to zero.
        step: update rate.

      Returns:
        The approximated value for root of the function.
  """
  der_val = der(theta_0, variable_group)
  fun_val = fun(theta_0, variable_group)
  inv = pinv(der_val)
  dot = inv.dot(fun_val)
  theta_n = theta_0 - step * dot
  i = 1
  while i < n_iter and not allclose(theta_n, zeros(theta_0.shape), atol=eps):
    theta_0 = theta_n
    der_val = der(theta_0, variable_group)
    fun_val = fun(theta_0, variable_group)
    inv = pinv(der_val)
    dot = inv.dot(fun_val)
    theta_n = theta_0 - step * dot
    i += 1
  return theta_n 

