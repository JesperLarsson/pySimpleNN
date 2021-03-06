# -*- coding: utf-8 -*-
# Copyright Jesper Larsson, Linköping, 2017-2018, github.com/JesperLarsson

"""
CONFIGURATION
"""
# Training
target_accuracy = 99.9 # percentage training confidence
max_training_time = 0 # training timeout in seconds, 0 = no timeout

# Algorithm tweaks
dynamic_alpha = True
starting_alpha = 10 # relative change performed on each delta, lower values makes us less likely to "overshoot" our target minimum, but it can take longer to get close to the result we want. 1 = no alpha

use_dropout = True
dropout_percent = 0.1

use_bias = False # bias not fully implemented yet, has no dynamic weights
synapse_bias = -1.0 # typically 1.0 or -1.0, allows an offset of each layer: https://stackoverflow.com/questions/2480650/role-of-bias-in-neural-networks

# Network layout
hidden_layers = 2 # number of hidden layers
hidden_dimensions = 4

# Input and output dimensions are inherintly tied to the training data
input_dimensions = 3
output_dimensions = 1

# Misc
sleeptime_ms = 1 # so we don't freeze up the computer

"""
SETUP
"""
import sys
if sys.version_info[0] < 3:
   print("You are running an old version of Python which is not compatible with this script. Please install Python version 3 or higher")
   raw_input("Press enter to exit") # We use raw_input, normal input function is dangerous in Python 2.X (but not Python 3)
   sys.exit(1)

try:
      import numpy as np
except ImportError:
   try:
      # Try to install it via package manager
      print("Installing numpy...")
      import pip
      pip.main(['install', "numpy"])
      import numpy as np
   except ImportError:
      print("Unable to install numpy, install manully using 'pip install numpy' in path C:\Python3\Scripts")
      input("Press enter to exit")
      sys.exit(2)

from math import *
from datetime import *
import time

np.random.seed(1) # easier debugging without true seed
nl = "\n"

alpha = starting_alpha

layer_count = hidden_layers + 2 # + input + output

"""
TEST DATA
"""
# Each row is a training sample of 3 input nodes each (3x1 matrix)
input_tests = np.array([
                [0,0,1],   
                [0,1,1],
                [1,0,1],
                [1,1,1],
                [1,0,1],
                [0,0,1],
                [1,0,1],
                [1,0,1],
                ])
# Expected values, T function (transpose) switches columns for rows
expected_outputs = np.array([[0,0,1,1,1,0,1,1]]).T

"""
FUNCTIONS AND CLASSES
"""
# Sigmoid activation function and its derivative (maps any value to non-linear space between 0 and 1)
def sigmoid(x):
    return 1/(1+np.exp(-x))
def sigmoid_slope(x):
    return x*(1-x)

def cost_function(target, calculated):
   cost = target - calculated

   return cost

# Connection between two layers
class Synapse:
   weights = None
   input_dimensions = 0
   output_dimensions = 0
   name = "N/A"

   def __init__(self, synapse_input_dimensions, synapse_output_dimensions, synapse_name):
      # Randomize synapse weights with mean value = 0
      self.weights = 2*np.random.random((synapse_input_dimensions, synapse_output_dimensions)) - 1
      self.input_dimensions = synapse_input_dimensions
      self.output_dimensions = synapse_output_dimensions

      self.name = synapse_name
      print("  Created " + self.name + "(" + str(synapse_input_dimensions) + " inputs / " + str(synapse_output_dimensions) + " outputs)")

class Layer:
      neurons = None

      # axons
      next_layer = None
      previous_layer = None
      synapse_to_next_layer = None

      name = "N/A"
      error_rate = 1.0

      def __init__(self, layer_name):
         print("  Created " + layer_name)
         self.name = layer_name

      # Simple implementation of Hinton's dropout algorithm
      #   This optimizes away some edge cases where multiple search paths are converging towards the same (local) minimum by discarding some connections at random
      #   Taken from here: http://iamtrask.github.io/2015/07/28/dropout/
      def perform_dropout(self):
         if (self.previous_layer is None):
            # No dropout for input layer
            return
         elif (self.next_layer is None):
            # No dropout for output layer
            return
         
         # Binomial picks some values at random in the given matrixes
         self.neurons *= np.random.binomial( [ np.ones((len(self.previous_layer.neurons),hidden_dimensions)) ], 1-dropout_percent)[0] * (1.0/(1-dropout_percent))

      # Forward propagate our values to the next layer
      def forward_propagation(self):
         if (self.next_layer is None):
            return # this layer does non forward propagate (output layer)

         weighted_neurons = np.dot(self.neurons, self.synapse_to_next_layer.weights)
         if (use_bias):
            weighted_neurons = (weighted_neurons + synapse_bias)

         print (str(weighted_neurons))

         self.next_layer.neurons = sigmoid( weighted_neurons )
    
      # Back propagate synapse weight deltas from the backmost layer
      #   Recursive implementation, call on first(!) layer to update the entire chain
      def back_propagation(self):
         if (self.next_layer is None):
            # "Confidence weighted error":
            #   This is the last layer, it compares to expected test data rather than to the next layer and never has a synapse to update            
            self.error_rate = cost_function(expected_outputs, self.neurons)
            weights_delta = self.error_rate * sigmoid_slope(self.neurons)
            
            return weights_delta
         else:
            # "Error weighted derivative":
            #   Error differences are calculated from the adjustments we made to the next layer
            #   This is the normal case for input and hidden layers
            next_layer_delta = self.next_layer.back_propagation()

            self.error_rate = next_layer_delta.dot(self.synapse_to_next_layer.weights.T)
            weights_delta = self.error_rate * sigmoid_slope(self.neurons)

            # Adjust weights from this to the next layer
            #   It's important we perform the changes AFTER we calculate our delta, since we want to adjust the previous layer based on the test deltas pre-adjustment
            self.synapse_to_next_layer.weights += alpha * ( self.neurons.T.dot(next_layer_delta) )

            return weights_delta

# Top level object
class Network:
   layers = []
   synapses = []
   training_mode = True

   # One network analyzation step, used for both training and real use
   def network_tick(self):
      # Forward propagate node values
      [l.forward_propagation() for l in self.layers]

      # Dropout (optimization) - only use dropout when training
      if (self.training_mode and use_dropout):
        [l.perform_dropout() for l in self.layers]

      # Calculate synapse weight deltas
      self.layers[0].back_propagation()

   def load_test_data(self):
      testdata = input_tests

      # Insert bias value
      #if (use_bias):
      #   testdata = insert_bias(testdata)

      self.layers[0].neurons = testdata
      return len(self.layers[0].neurons)

   # Return debug string of the entire network
   def to_string(self, include_layers = False, include_synapses = True):
      output = ""

      layer_counter = 0
      for layer in self.layers:
         # Layer neurons
         if (include_layers):
            output += layer.name + ":" + nl

            if (layer is None or layer.neurons is None):
               output += "  Uninitialized" + nl
            else:
               for neuron in layer.neurons:
                  output += "  " + str(neuron) + nl
            output += nl

         # Synapse weights
         if (include_synapses and layer.synapse_to_next_layer is not None):
            output += layer.synapse_to_next_layer.name + ":" + nl

            fromnode_w_counter = 0
            for fromnode_w in layer.synapse_to_next_layer.weights:
               output += "  From Node " + str(fromnode_w_counter) + ":" + nl
               tonode_w_counter = 0
               for tonode_w in fromnode_w:
                  output += "    To Node " + str(tonode_w_counter) + ": " + str(tonode_w) + nl
                  tonode_w_counter += 1

               fromnode_w_counter += 1

            output += nl

         layer_counter += 1

      return output

   # Trains the network until a sufficiently high accuracy has been achieved
   def main_loop_training(self):
      start_time = datetime.now()
      last_trace = 0
      iteration = 0
      while(True):
         iteration += 1

         self.network_tick()
         network_error_rate = self.layers[-1].error_rate

         # Print intermittently
         current_accuracy = 100 * (1 - (np.mean(np.abs(network_error_rate))))
         uptime = (datetime.now() - start_time).total_seconds()
         if (int(uptime) > int(last_trace) or iteration <= 5):
           print("  Iteration " + str(iteration) + " accuracy: " + str(current_accuracy) + "%")
           last_trace = uptime

          # We're done
         if (current_accuracy >= target_accuracy):
           print("  Achieved target " + str(target_accuracy) + "% accuracy after " + str(iteration) +
                 " training steps " + 
                 "in " + str(uptime) + "s")
           return True

         # Timeout
         if (uptime > max_training_time and max_training_time != 0):
           print("  TIMEOUT after " + str(iteration) +
                 " training steps with average test accuracy: " + str(current_accuracy) +
                 "% in " + str(uptime) + "s")
           return False

         time.sleep(sleeptime_ms / 1000)

   def __init__(self):
      # Create layers
      for iter in range(layer_count):
         new_layer = Layer("Layer " + str(iter))
         self.layers.append(new_layer)

         # Set linked list pointers
         if (iter > 0):
            self.layers[iter - 1].next_layer = new_layer
            new_layer.previous_layer = self.layers[iter - 1]

      # Create synapses between layers
      for iter in range(layer_count - 1):
         synapse_input_dimensions = hidden_dimensions
         synapse_output_dimensions = hidden_dimensions
         synapse_name = "Synapse L" + str(iter) + " => L" + str(iter + 1)

         if (iter == 0):
            # First obj special case
            synapse_input_dimensions = input_dimensions

         if (iter == (layer_count - 2)):
            # Last obj special case
            synapse_output_dimensions = output_dimensions

         # Add bias dimension
         #if (use_bias):
         #   synapse_input_dimensions += 1

         new_synapse = Synapse(synapse_input_dimensions, synapse_output_dimensions, synapse_name)
         self.synapses.append(new_synapse)

         # Add synapse pointer to layer, last layer has no synapse
         self.layers[iter].synapse_to_next_layer = new_synapse


            


"""
CODE ENTRY POINT
"""
print("===== INITIATING NETWORK")
network = Network()
test_count = network.load_test_data()
print("  Loaded " + str(test_count) + " test samples")
print("")

#print("===== RANDOMIZED STARTING NETWORK")
#print(network.to_string())
#print("")

# Start training
print("===== TRAINING")
print("  Targeting " + str(target_accuracy) + "% training accuracy")
success = network.main_loop_training()
if (success):
   network.training_mode = False
print("")

print("===== TRAINED NETWORK")
print(network.to_string())
print("")

# Trace test results, this trace only supports 1-dimension outputs
print("===== TRAINING CASES RESULTS")
output_neurons = network.layers[-1].neurons
for i in range(len(output_neurons)):
    output_value = output_neurons[i][0]
    expected_value = expected_outputs[i][0]
    value_diff = fabs(expected_value - output_value)
    print("  Test " + (str(i + 1)) + ". " + str(output_value) + ". Expected " + str(expected_value) + ". Diff = " + str(value_diff))
print("")
