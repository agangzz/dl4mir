"""
"""


import json
import numpy as np
import os

import theano
import theano.tensor as T
from theano.tensor.shared_randomstreams import RandomStreams
from theano.tensor.signal import downsample

from ejhumphrey.dnn.core import FLOATX
from ejhumphrey.dnn.core import functions


def Layer(layer_args):
    """Layer factory; uses 'type' in the layer_args dictionary."""
    return eval("%s(layer_args)" % layer_args.get("type"))


# --- Layer Argument Classes ---
class BaseLayerArgs(dict):
    """
    Base class for all layer arguments
    """

    INPUT_SHAPES = 'input_shapes'
    OUTPUT_SHAPES = 'output_shapes'
    PARAM_SHAPES = 'param_shapes'
    NAME = 'name'
    ACTIVATION = 'activation'
    TYPE = 'type'

    def __init__(self, name,
                 input_shapes=None,
                 output_shapes=None,
                 param_shapes=None,
                 activation="linear"):
        """
        Parameters
        ----------
        name : str
            Unique name for the layer.
        input_shapes : dict of tuples
            Dimensions of the layer's primary inputs.
        activation : string
            Name of the activation function.
        """
        assert activation in functions.Activations, \
            "Given activation '%s' is undefined."

        if param_shapes is None:
            param_shapes = dict()
        if input_shapes is None:
            input_shapes = dict()
        if output_shapes is None:
            output_shapes = dict()

        args = {BaseLayerArgs.TYPE: self.type,
                BaseLayerArgs.NAME: name,
                BaseLayerArgs.PARAM_SHAPES: param_shapes,
                BaseLayerArgs.INPUT_SHAPES: input_shapes,
                BaseLayerArgs.OUTPUT_SHAPES: output_shapes,
                BaseLayerArgs.ACTIVATION: activation, }

        self.update(args)

    def __str__(self):
        return json.dumps(self)

    @property
    def type(self):
        return self.__class__.__name__.split("Args")[0]

    def Layer(self):
        return eval(self.type)(self)

    @property
    def name(self):
        return self.get(self.NAME)

    @property
    def activation(self):
        return self.get(self.ACTIVATION)

    @property
    def input_shapes(self):
        """
        Returns
        -------
        shp : tuple
        """
        return self.get(self.INPUT_SHAPES)

    # Necessary?
    @property
    def input_names(self):
        return self.input_shapes.keys()

    @property
    def output_shapes(self):
        """
        Returns
        -------
        shp : tuple
        """
        return self.get(self.OUTPUT_SHAPES)

    # Necessary?
    @property
    def output_names(self):
        return self.output_shapes.keys()

    @property
    def param_shapes(self):
        return self.get(self.PARAM_SHAPES)

    @param_shapes.setter
    def param_shapes(self, shapes):
        """
        Parameters
        ----------
        shapes : dict
        """
        self[self.PARAM_SHAPES].update(shapes)

    @property
    def param_names(self):
        return self.param_shapes.keys()


class AffineArgs(BaseLayerArgs):
    """
    """
    INPUT = 'x_input'
    OUTPUT = 'z_output'
    WEIGHTS = 'weights'
    BIAS = 'bias'

    def __init__(self, name, weight_shape, activation="tanh"):
        """
        Parameters
        ----------
        name: str
            asdf
        weight_shape: tuple
            Shape of the affine transform, (n_in, n_out)
        activation: str
            asdf
        """
        BaseLayerArgs.__init__(
            self,
            name=name,
            input_shapes={AffineArgs.INPUT: weight_shape[:1]},
            output_shapes={AffineArgs.OUTPUT: weight_shape[1:]},
            param_shapes={AffineArgs.WEIGHTS: weight_shape,
                          AffineArgs.BIAS: weight_shape[1:]},
            activation=activation)


class SoftmaxArgs(AffineArgs):
    """
    """
    def __init__(self, name,
                 input_dim,
                 output_dim,
                 activation='linear'):
        """
        """
        AffineArgs.__init__(self, name,
                            weight_shape=(input_dim, output_dim),
                            activation=activation)


class Conv3DArgs(BaseLayerArgs):

    INPUT = 'x_input'
    OUTPUT = 'z_output'
    WEIGHTS = 'weights'
    BIAS = 'bias'
    POOL = 'pool'
    DOWNSAMPLE = 'downsample'
    BORDER_MODE = 'border_mode'

    def __init__(self, name,
                 input_shape,
                 weight_shape,
                 pool_shape=(1, 1),
                 downsample_shape=(1, 1),
                 activation="tanh",
                 border_mode='valid'):
        """
        Parameters
        ----------
        input_shape : tuple
            Shape of the input data, as (in_maps, in_dim0, in_dim1).
        weight_shape : tuple
            Shape for all kernels, as (num_kernels, w_dim0, w_dim1).
        pool_shape : tuple
            2D tuple to pool over each feature map, as (p_dim0, p_dim1).
        downsample_shape : tuple
            2D tuple for downsampling each feature map, as (p_dim0, p_dim1).
        activation : str
            Name of the activation function to use.
        border_mode : str
            Convolution method for dealing with the edge of a feature map.
        """
        # If input_shape is provided, must make sure the weight_shape is
        # consistent.
        if input_shape:
            w = list(weight_shape)
            if len(w) == 3:
                w.insert(1, input_shape[0])
            elif len(w) == 4:
                w[1] = input_shape[0]
            weight_shape = tuple(w)

        param_shapes = {Conv3DArgs.WEIGHTS: weight_shape,
                        Conv3DArgs.BIAS: weight_shape[:1], }
        d0_in, d1_in = input_shape[1:]
        d0_out = int(d0_in - weight_shape[-2] + 1) / pool_shape[0]
        d1_out = int(d1_in - weight_shape[-1] + 1) / pool_shape[1]
        output_shape = (weight_shape[0], d0_out, d1_out)

        BaseLayerArgs.__init__(self, name,
                               input_shapes={Conv3DArgs.INPUT: input_shape},
                               output_shapes={Conv3DArgs.OUTPUT: output_shape},
                               param_shapes=param_shapes,
                               activation=activation)
        self.update({Conv3DArgs.POOL: pool_shape,
                     Conv3DArgs.DOWNSAMPLE: downsample_shape,
                     Conv3DArgs.BORDER_MODE: border_mode})

    # # Necessary?
    # @property
    # def pool_shape(self):
    #     return self.get(Conv3DArgs.POOL)

    # # Necessary?
    # @property
    # def downsample_shape(self):
    #     return self.get(Conv3DArgs.DOWNSAMPLE)

    # Necessary?
    @property
    def weight_shape(self):
        return self.param_shapes.get("weights")


class MultiSoftmaxArgs(AffineArgs):
    """
    """
    def __init__(self, name,
                 input_shape,
                 output_shape,
                 activation='linear'):
        """
        Parameters
        ----------
        name : str
            Identifier for this layer.
        input_shape : tuple
            Input shape, flattened to 1D.
        output_shape : tuple
            (n_softmaxes, output_dim)
        """
        n_in = np.prod(input_shape, dtype=int)
        assert len(output_shape) == 2
        weight_shape = (output_shape[0], n_in, output_shape[1])
        BaseLayerArgs.__init__(self, name=name,
                               input_shape=(n_in,),
                               param_shapes=dict(weights=weight_shape,
                                                 bias=output_shape),
                               activation=activation)
        self.update(input_shape=self.input_shape,
                    output_shape=self.output_shape)

    @property
    def output_shape(self):
        return (self.weight_shape[0], self.weight_shape[2])

    @property
    def weight_shape(self):
        return self.param_shapes.get("weights")


class RBFArgs(AffineArgs):
    """
    """
    def __init__(self, name,
                 input_dim,
                 output_dim,
                 lp_norm='l1',
                 activation='linear'):
        """
        """
        AffineArgs.__init__(self, name,
                            input_shape=(input_dim,),
                            output_shape=(output_dim,),
                            activation=activation)
        del self['param_shapes']['bias']
        self.update(lp_norm=lp_norm)


# --- Layer Class Implementations ------
class BaseLayer(dict):
    """
    Layers are in charge of parameter management and micro-math operations.
    """

    # REQUIRED_INPUTS = []
    def __init__(self, layer_args):
        """
        layer_args: dict
            Needs input validation.
        """
        self.update(layer_args)

        # TODO(ejhumphrey): Input validation is desperately needed.
        self.numpy_rng = np.random.RandomState()
        self.theano_rng = RandomStreams(self.numpy_rng.randint(2 ** 30))

        # Theta is the local set of all symbolic parameters in this layer.

        self._params = dict([(k, None)
                             for k in self.get('param_shapes').keys()])

        # TODO(ejhumphrey): Make the dropout variable more agnostic, if this
        #     is the way things are going to proceed.
        self._scalars = dict(dropout=T.scalar(name=self.own("dropout"),
                                              dtype=FLOATX))
        self._inputs = dict([(k, None)
                             for k in self.get('input_shapes').keys()])
        self._outputs = dict([(k, None)
                              for k in self.get('output_shapes').keys()])

    def __str__(self):
        return json.dumps(self, indent=2)

    @property
    def name(self):
        return self.get("name")

    def own(self, name):
        return os.path.join(self.name, name)

    @property
    def type(self):
        # Deprecated / unnecessary?
        return self.__class__.__name__

    @property
    def activation(self):
        # Is it really necessary to expose this?
        return functions.Activations.get(self.get("activation"))

    @property
    def params(self):
        """
        The symbolic parameters of the layer.

        Returns
        -------
        params : dict
            Symbolic parameters of the layer, keyed by full name.
        """
        return dict([(self.own(k), v) for k, v in self._params.iteritems()])

    @property
    def param_values(self):
        """
        The numeric parameters of the layer.

        Returns
        -------
        values : dict
            np.ndarray values of the layer, keyed by full-name.

        """
        return dict([(k, v.get_value()) for k, v in self.params.iteritems()])

    @param_values.setter
    def param_values(self, param_values):
        """
        Parameters
        ----------
        param_values : dict
            key/value pairs of parameter name and np.ndarray

        """
        for full_name, value in param_values.items():
            layer_name, param_name = os.path.split(full_name)
            # Bypass all values that do not correspond to this layer.
            if self.name != layer_name:
                continue
            if not param_name in self._params:
                # Catch undeclared parameters.
                raise ValueError("Undeclared parameter: %s" % param_name)
            elif self._params[param_name] is None:
                # Declared but uninitialized; safe to do so now.
                self._params[param_name] = theano.shared(
                    value=value.astype(FLOATX), name=full_name)
            else:
                # Initialized, but changing value.
                self._params[param_name].set_value(value.astype(FLOATX))

    @property
    def scalars(self):
        return dict([(self.own(k), v)
                     for k, v in self._scalars.iteritems()])

    @property
    def inputs(self):
        return dict([(self.own(k), v)
                     for k, v in self._inputs.iteritems()])

    @property
    def outputs(self):
        return dict([(self.own(k), v)
                     for k, v in self._outputs.iteritems()])

    @property
    def input_shapes(self):
        """
        Returns
        -------
        shapes : dict
        """
        return dict([(self.own(k), v)
                     for k, v in self.get("input_shapes").iteritems()])

    @property
    def output_shapes(self):
        """
        Returns
        -------
        shapes : dict
        """
        return dict([(self.own(k), v)
                     for k, v in self.get("output_shapes").iteritems()])

    @property
    def param_shapes(self):
        return dict([(self.own(k), v)
                     for k, v in self.get("param_shapes").iteritems()])

    def transform(self, inputs):
        """
        inputs : dict of named Theano variables

        Must cache inputs, set / configure outputs.
        """
        raise NotImplementedError("Subclass me!")

    # TODO(ejhumphrey): Is this deprecated / the best way to do this?
    @property
    def dropout(self):
        """
        Used as a probability.
        """
        return self._scalars.get("dropout")


class Affine(BaseLayer):
    """
    Affine Transform Layer
      (i.e., a fully-connected non-linear projection)

    """

    def __init__(self, layer_args):
        """
        layer_args : AffineArgs

        """
        BaseLayer.__init__(self, layer_args)
        weight_shape = self.get("param_shapes")[AffineArgs.WEIGHTS]
        weight_values = self.numpy_rng.normal(
            loc=0.0,
            scale=np.sqrt(1.0 / np.sum(weight_shape)),
            size=weight_shape)
        bias_values = np.zeros(self.get("param_shapes")[AffineArgs.BIAS])
        self.param_values = {self.own(AffineArgs.WEIGHTS): weight_values,
                             self.own(AffineArgs.BIAS): bias_values, }

    def transform(self, inputs):
        """
        will fix input tensors to be matrices as the following:
        (N x d0 x d1 x ... dn) -> (N x prod(d_(0:n)))

        """
        outputs = dict()
        x_in = inputs.get(self.own(AffineArgs.INPUT), None)
        if x_in is None:
            return outputs
        # self._inputs[AffineArgs.INPUT] = x_in
        W = self._params[AffineArgs.WEIGHTS]
        b = self._params[AffineArgs.BIAS].dimshuffle('x', 0)
        # TODO(ejhumphrey): This isn't very stable, is it.
        x_in = T.flatten(x_in, outdim=2)
        z_out = self.activation(T.dot(x_in, W) + b)

        output_shape = self.get(AffineArgs.OUTPUT_SHAPES)[AffineArgs.OUTPUT]
        selector = self.theano_rng.binomial(size=output_shape,
                                            p=1.0 - self.dropout,
                                            dtype=FLOATX)
        z_out = z_out * selector.dimshuffle('x', 0) * (self.dropout + 0.5)
        z_out.name = self.own(AffineArgs.OUTPUT)
        outputs[z_out.name] = z_out
        return outputs
        # self._outputs[AffineArgs.OUTPUT] = z_out
        # return self.outputs


class RBF(BaseLayer):
    """
    Radial Basis Function Layer
      (i.e. distance layer)

    """
    param_names = ["weights"]

    def __init__(self, layer_args):
        """
        layer_args : RBFArgs

        """
        BaseLayer.__init__(self, layer_args)
        w_shape = self.param_shapes.get("weights")
        weights = self.numpy_rng.normal(loc=0.0,
                                        scale=np.sqrt(1. / np.sum(w_shape)),
                                        size=w_shape)
        self.param_values = {self.own('weights'): weights, }

    def transform(self, x_in):
        """
        will fix input tensors to be matrices as the following:
        (N x d0 x d1 x ... dn) -> (N x prod(d_(0:n)))

        """
        W = self._theta["weights"].T

        # TODO(ejhumphrey): This isn't very stable, is it.
        x_in = T.flatten(x_in, outdim=2)
        if self.get("lp_norm") == "l1":
            z_out = T.abs_(x_in.dimshuffle(0, 'x', 1) - W.dimshuffle('x', 0, 1))
        elif self.get("lp_norm") == "l2":
            z_out = T.pow(x_in.dimshuffle(0, 'x', 1) - W.dimshuffle('x', 0, 1), 2.0)
        else:
            raise NotImplementedError(
                "Lp_norm type '%s' unsupported." % self.get("lp_norm"))

        selector = self.theano_rng.binomial(size=self.output_shape,
                                            p=1.0 - self.dropout,
                                            dtype=FLOATX)
        return T.sum(z_out, axis=2) * selector.dimshuffle('x', 0) * (self.dropout + 0.5)


class Conv3D(BaseLayer):
    """ (>^.^<) """

    def __init__(self, layer_args):
        """
        layer_args : dict

        """
        BaseLayer.__init__(self, layer_args)

        # Create all the weight values at once
        param_shapes = layer_args.get(Conv3DArgs.PARAM_SHAPES)
        weight_shape = param_shapes.get(Conv3DArgs.WEIGHTS)
        fan_in = np.prod(weight_shape[1:])
        weight_values = self.numpy_rng.normal(
            loc=0.0, scale=np.sqrt(3. / fan_in), size=weight_shape)

        if self.get(Conv3DArgs.ACTIVATION) == 'sigmoid':
            weight_values *= 4

        bias_values = np.zeros(weight_shape[0])
        self.param_values = {self.own(Conv3DArgs.WEIGHTS): weight_values,
                             self.own(Conv3DArgs.BIAS): bias_values, }

    def transform(self, inputs):
        """

        """
        x_in = inputs.get(self.own(Conv3DArgs.INPUT))
        self._inputs[Conv3DArgs.INPUT] = x_in

        weights = self._params[Conv3DArgs.WEIGHTS]
        bias = self._params[Conv3DArgs.BIAS].dimshuffle('x', 0, 'x', 'x')

        param_shapes = self.get(Conv3DArgs.PARAM_SHAPES)
        z_out = T.nnet.conv.conv2d(
            input=x_in,
            filters=weights,
            filter_shape=param_shapes.get(Conv3DArgs.WEIGHTS),
            border_mode=self.get(Conv3DArgs.BORDER_MODE))

        output_shape = self.get(Conv3DArgs.OUTPUT_SHAPES)[Conv3DArgs.OUTPUT]
        selector = self.theano_rng.binomial(size=output_shape[:1],
                                            p=1.0 - self.dropout,
                                            dtype=FLOATX)

        z_out = self.activation(z_out + bias)
        z_out *= selector.dimshuffle('x', 0, 'x', 'x') * (self.dropout + 0.5)
        z_out = downsample.max_pool_2d(
            z_out, self.get(Conv3DArgs.POOL), ignore_border=False)
        z_out.name = self.own(Conv3DArgs.OUTPUT)
        self._outputs[Conv3DArgs.OUTPUT] = z_out
        return z_out


class Conv2D(BaseLayer):
    """ . """

    def __init__(self, layer_args):
        """
        layer_args : ConvArgs

        """
        BaseLayer.__init__(self, layer_args)

        # Create all the weight values at once
        weight_shape = self.param_shapes.get("weights")
        fan_in = np.prod(weight_shape[1:])
        weights = self.numpy_rng.normal(loc=0.0,
                                        scale=np.sqrt(3. / fan_in),
                                        size=weight_shape)

        if self.get("activation") == 'sigmoid':
            weights *= 4

        bias = np.zeros(weight_shape[0])
        self.param_values = {self.own('weights'): weights,
                             self.own('bias'): bias, }

    def transform(self, x_in):
        """

        """
        W = self._theta['weights']
        b = self._theta['bias']
        weight_shape = self.param_shapes.get("weights")
        z_out = T.nnet.conv.conv2d(input=x_in,
                                   filters=W,
                                   filter_shape=weight_shape,
                                   border_mode=self.get("border_mode"))

        selector = self.theano_rng.binomial(size=self.output_shape[:1],
                                            p=1.0 - self.dropout,
                                            dtype=FLOATX)

        z_out = self.activation(z_out + b.dimshuffle('x', 0, 'x', 'x'))
        z_out *= selector.dimshuffle('x', 0, 'x', 'x') * (self.dropout + 0.5)
        return downsample.max_pool_2d(
            z_out, self.get("pool_shape"), ignore_border=False)


class Softmax(BaseLayer):
    """
    """
    param_names = ["weights", "bias"]

    def __init__(self, layer_args):
        """
        """
        BaseLayer.__init__(self, layer_args)
        w_shape = self.param_shapes.get("weights")
        scale = np.sqrt(6. / np.sum(w_shape))

        weights = self.numpy_rng.normal(loc=0.0, scale=scale, size=w_shape)
        bias = np.zeros(self.output_shape)

        self.param_values = {self.own('weights'): weights,
                             self.own('bias'): bias, }
        self._scalars.clear()

    def transform(self, x_in):
        """
        will fix input tensors to be matrices as the following:
        (N x d0 x d1 x ... dn) -> (N x prod(d_(0:n)))
        """
        # TODO(ejhumphrey): This isn't very stable, is it.
        x_in = x_in.flatten(2)
        W = self._theta["weights"]
        b = self._theta["bias"].dimshuffle('x', 0)
        return T.nnet.softmax(self.activation(T.dot(x_in, W) + b))


class SoftMask(BaseLayer):
    """
    """
    param_names = ["weights", "bias", "templates"]

    def __init__(self, layer_args):
        """
        """
        BaseLayer.__init__(self, layer_args)
        weight_shape = self.param_shapes.get("weights")
#        scale = np.sqrt(6. / np.sum(weight_shape))

#        weights = self.numpy_rng.normal(loc=1.0,
#                                        scale=0.05,
#                                        size=weight_shape)
        weights = self.numpy_rng.uniform(low=0, high=1.0, size=weight_shape)
        templates = np.ones(weights.shape)
        bias = np.zeros(self.output_shape)

        self.param_values = {self.own('weights'): weights,
                             self.own('bias'): bias,
                             self.own('templates'): templates, }
        self._scalars.clear()

    def transform(self, x_in):
        """
        will fix input tensors to be matrices as the following:
        (N x d0 x d1 x ... dn) -> (N x prod(d_(0:n)))
        """
        # TODO(ejhumphrey): This isn't very stable, is it.
        x_in = x_in.flatten(2)
        W = self._theta["weights"] * self._theta["templates"]
        b = self._theta["bias"].dimshuffle('x', 0)
        return T.nnet.softmax(self.activation(T.dot(x_in, W) + b))


class MultiSoftmax(BaseLayer):
    """
    Multi-softmax Layer


    """
    param_names = ["weights", "bias"]

    def __init__(self, layer_args):
        """
        layer_args : AffineArgs

        """
        BaseLayer.__init__(self, layer_args)
        w_shape = self.param_shapes.get("weights")
        weights = self.numpy_rng.normal(loc=0.0,
                                        scale=np.sqrt(1. / np.sum(w_shape)),
                                        size=w_shape)
        bias = np.zeros(self.output_shape)
        self.param_values = {self.own('weights'): weights,
                             self.own('bias'): bias, }
        self._scalars.clear()

    def transform(self, x_in):
        """
        will fix input tensors to be matrices as the following:
        (N x d0 x d1 x ... dn) -> (N x prod(d_(0:n)))

        """
        W = self._theta["weights"]
        b = self._theta['bias']

        x_in = T.flatten(x_in, outdim=2)
        output = []
        for i in range(self.output_shape[0]):
            z_i = self.activation(T.dot(x_in, W[i]) + b[i].dimshuffle('x', 0))
            output.append(T.nnet.softmax(z_i).dimshuffle(0, 1, 'x'))

        return T.concatenate(output, axis=2)


class EnergyPDF(BaseLayer):
    """
    """
    param_names = []

    def __init__(self, layer_args):
        """
        """
        BaseLayer.__init__(self, layer_args)
        self.param_values = {}
        self._scalars.clear()

    def transform(self, x_in):
        """
        will fix input tensors to be matrices as the following:
        (N x d0 x d1 x ... dn) -> (N x prod(d_(0:n)))
        """
        return T.nnet.softmax(-1.0 * x_in)
