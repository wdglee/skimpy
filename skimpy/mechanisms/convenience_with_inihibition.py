# -*- coding: utf-8 -*-
"""
.. module:: skimpy
   :platform: Unix, Windows
   :synopsis: Simple Kinetic Models in Python

.. moduleauthor:: SKiMPy team

[---------]

Copyright 2017 Laboratory of Computational Systems Biotechnology (LCSB),
Ecole Polytechnique Federale de Lausanne (EPFL), Switzerland

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

"""


from sympy import sympify

from .mechanism import KineticMechanism,ElementrayReactionStep
from ..core.reactions import Reaction
from ..utils.tabdict import TabDict
from collections import namedtuple
from ..core.itemsets import make_parameter_set, make_reactant_set
from skimpy.utils.general import make_subclasses_dict
from ..utils.namespace import *
from .utils import stringify_stoichiometry


def make_convenience_with_inhibition(stoichiometry, inihbitor_stoichiometry):

    """

    :param stoichiometry is a list of the reaction stoichioemtry
    """
    ALL_MECHANISM_SUBCLASSES = make_subclasses_dict(KineticMechanism)

    new_class_name = "Convenience"\
                     + "_{0}".format(stringify_stoichiometry(stoichiometry,
                                                             inihibitors=inihbitor_stoichiometry))

    if new_class_name in ALL_MECHANISM_SUBCLASSES.keys():
        return ALL_MECHANISM_SUBCLASSES[new_class_name]

    class ConvenienceInhibited(KineticMechanism):
        """A reversible N-M enyme class with inhibitors as described in:

        Savoglidis, G., et al. (2016). "A method for analysis and design of metabolism using metabolomics
         data and kinetic models: Application on lipidomics using a novel kinetic model
         of sphingolipid metabolism." Metabolic Engineering 37: 46-62.

        """

        suffix = "_{0}".format(stringify_stoichiometry(stoichiometry,
                                                       inihibitors=inihbitor_stoichiometry))

        reactant_list = []
        inhibitor_list = []
        parameter_list = {'vmax_forward': [ODE, MCA, QSSA],
                          'k_equilibrium': [ODE, MCA, QSSA], }

        parameter_reactant_links = {}
        reactant_stoichiometry = {}

        num_substrates = 1
        num_products = 1
        num_inhibitors = 1

        for s in stoichiometry:
            if s < 0:
                substrate = 'substrate{}'.format(num_substrates)
                km_substrate ='km_substrate{}'.format(num_substrates)
                reactant_list.append(substrate)
                parameter_list[km_substrate] = [ODE, MCA, QSSA]
                parameter_reactant_links[km_substrate] = substrate
                reactant_stoichiometry[substrate] = float(s)
                num_substrates += 1

            if s > 0:
                product = 'product{}'.format(num_products)
                km_product ='km_product{}'.format(num_products)
                reactant_list.append(product)
                parameter_list[km_product] = [ODE, MCA, QSSA]
                parameter_reactant_links[km_product] = product
                reactant_stoichiometry[product] = float(s)
                num_products += 1

        for i in inihbitor_stoichiometry:
            inhibitor = 'inhibitor{}'.format(num_inhibitors)
            ki_inhibitor = 'ki_inhibitor{}'.format(num_inhibitors)
            inhibitor_list.append(inhibitor)
            parameter_list[ki_inhibitor] = [ODE, MCA, QSSA]
            parameter_reactant_links[ki_inhibitor] = inhibitor
            #reactant_stoichiometry[inhibitor] = 0.0
            num_inhibitors += 1

        Reactants = make_reactant_set(__name__ + suffix, reactant_list)

        Inhibitors = make_reactant_set(__name__ + suffix, inhibitor_list)

        Parameters = make_parameter_set(__name__ + suffix, parameter_list)

        ElementaryReactions = namedtuple('ElementaryReactions',[])


        def __init__(self, name, reactants, inhibitors, parameters=None):
            # FIXME dynamic linking, separaret parametrizations from model init
            # FIXME Reaction has a mechanism, and this is a mechanism
            KineticMechanism.__init__(self, name, reactants, parameters, inhibitors=inhibitors)

        def get_qssa_rate_expression(self):
            reactant_km_relation = { }

            for k, v in self.parameter_reactant_links.items():
                if (v in self.reactants):
                    reactant_km_relation[self.reactants[v].symbol] = k
                elif (v in self.inhibitors):
                    reactant_km_relation[self.inhibitors[v].symbol] = k
                else:
                    raise KeyError('Link not defined in any list')

            substrates = {k:r for k,r in self.reactants.items()
                          if k.startswith('substrate')}

            products= {k:r for k,r in self.reactants.items()
                          if k.startswith('product')}

            inhibitors = {k: r for k, r in self.inhibitors.items()
                          if k.startswith('inhibitor')}


            keq = self.parameters.k_equilibrium.symbol
            vmaxf = self.parameters.vmax_forward.symbol

            common_denominator_substrates = 1
            fwd_nominator = vmaxf
            bwd_nominator = vmaxf/keq

            for type, this_substrate in substrates.items():
                common_denominator_this_substrate = 1
                s = this_substrate.symbol
                kms = self.parameters[reactant_km_relation[s]].symbol
                stoich = self.reactant_stoichiometry[type]
                for alpha in range(int(abs(stoich))):
                    common_denominator_this_substrate += (s/kms)**(alpha+1)
                # Multiply for every substrate
                common_denominator_substrates *= common_denominator_this_substrate

                fwd_nominator *= (s/kms)**abs(stoich)
                bwd_nominator *= kms**(-1*abs(stoich))

            common_denominator_products = 1
            for type, this_product in products.items():
                common_denominator_this_product = 1
                p = this_product.symbol
                kmp = self.parameters[reactant_km_relation[p]].symbol
                stoich = self.reactant_stoichiometry[type]
                for beta in range(int(abs(stoich))):
                    common_denominator_this_product += (p/kmp)**(beta+1)
                # Multiply for every product
                common_denominator_products *= common_denominator_this_product

                bwd_nominator *= p**abs(stoich)

            common_denominator_inhibitors = 0
            for type, this_inhibitor in inhibitors.items():
                i = this_inhibitor.symbol
                kmi = self.parameters[reactant_km_relation[i]].symbol
                common_denominator_inhibitors += i/kmi

            common_denominator = common_denominator_substrates +\
                                 common_denominator_products - 1\
                                 + common_denominator_inhibitors

            forward_rate_expression = fwd_nominator/common_denominator
            backward_rate_expression = bwd_nominator/common_denominator
            rate_expression = forward_rate_expression-backward_rate_expression

            self.reaction_rates = TabDict([('v_net', rate_expression),
                                           ('v_fwd', forward_rate_expression),
                                           ('v_bwd', backward_rate_expression),
                                           ])

            expressions = {}

            # TODO Find a better solution to handle duplicate substrates
            # The dict currently does not allow for this
            for type, this_substrate in substrates.items():
                s = this_substrate.symbol
                stoich = self.reactant_stoichiometry[type]
                if s in expressions.keys():
                    expressions[s] += stoich * rate_expression
                else:
                    expressions[s] = stoich*rate_expression

            for type, this_product in products.items():
                p = this_product.symbol
                stoich = self.reactant_stoichiometry[type]
                if p in expressions.keys():
                    expressions[p] += stoich * rate_expression
                else:
                    expressions[p] = stoich*rate_expression

            self.expressions = expressions
            self.expression_parameters = self.get_parameters_from_expression(rate_expression)

        def update_qssa_rate_expression(self):

            substrates = {k:r for k,r in self.reactants.items()
                          if k.startswith('substrate')}

            products= {k:r for k,r in self.reactants.items()
                          if k.startswith('product')}
            
            expressions = {}
            for type, this_substrate in substrates.items():
                s = this_substrate.symbol
                stoich = self.reactant_stoichiometry[type]
                if s in expressions.keys():
                    expressions[s] += stoich * self.reaction_rates['v_net']
                else:
                    expressions[s] = stoich*self.reaction_rates['v_net']

            for type, this_product in products.items():
                p = this_product.symbol
                stoich = self.reactant_stoichiometry[type]
                if p in expressions.keys():
                    expressions[p] += stoich * self.reaction_rates['v_net']
                else:
                    expressions[p] = stoich * self.reaction_rates['v_net']

                self.expressions = expressions


        """"
        Convenience kinetics has no detailed mechanism 
        """
        def get_full_rate_expression(self):
            raise NotImplementedError

        def calculate_rate_constants(self):
            raise NotImplementedError

    ConvenienceInhibited.__name__ += ConvenienceInhibited.suffix

    return ConvenienceInhibited