================================
PyOracle improvisation + i-score
================================

Integration of the Max PyOracle interface with the intermedia sequence
i-score.

Installation
~~~~~~~~~~~~

In order to use `PyOracle <https://github.com/himito/PyOracle_I-score>`_, it is necessary to install the following tools:

- `Max/MSP <https://cycling74.com/>`_: Briefly, PyOracle is a Max
  patch allowing to play and capture in real-time the audio that will
  be processed by the python module of factor oracle.

- `Py <https://github.com/himito/py-mac>`_: The interface between
  Max/MSP and the Python implementation of factor oracle is carried
  out by the plugin Py. To install please refer to README file of the
  package.

For the communication with `i-score <https://github.com/OSSIA/i-score>`_, you need to install:

- `Jamoma <https://github.com/himito/Jamoma>`_: The communication between
  *Max/MSP* and `i-score <https://github.com/OSSIA/i-score>`_ is
  carried out by using the protocol *minuit*. In this regard, we need
  to install **jamoma**. To install please refer to this `video
  <https://vimeo.com/161361407>`_.
