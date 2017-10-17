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

from scipy.integrate import ode
from numpy import array, append

from .ode_fun import ODEFunction
from .solution import Solution

from ..utils import TabDict
from ..utils.general import join_dicts

def iterable_to_tabdict(iterable):
    return TabDict([(x.name, x) for x in iterable])

class KineticModel(object):
    # Consult with Pierre about this class!
    # Better use dicts with names! + inherited objects!

    def __init__(self, reactions = [], boundaries = []):
        # initialize the model is stated
        # FIXME Add dictlists from cobra ? or reimplement a similar data structure
        # self.metabolites = metabolites    #List of metabolite objects/ids

        # List of enzyme objects
        self.reactions   = iterable_to_tabdict(reactions)
        self.boundaries  = iterable_to_tabdict(boundaries)
        self._modifed    = True

    # TODO : Implement
    @property
    def metabolites(self):
        pass

    def add_reaction(self, reaction):
        # Add an enzyme to the model
        if reaction.name in self.reactions:
            error_msg = 'Reaction {} already exists in the model'
            raise(Exception(error_msg.format(reaction.name)))

        self.reactions[reaction.name] = reaction

        # TODO : Implement with metabolites
        # for this_metabolite in reaction.metabolites:
        #     self.metabolites.append(this_metabolite)
        self._modifed = True

    def parametrize(self,param_dict):
        """
        If has input: apply as dict to reactions in the model by
            reaction.parametrize(args)
        :return:
        """

        for reaction_name, the_params in param_dict.items():
            the_reaction = self.reactions[reaction_name]
            the_reaction.parametrize(the_params)

    def add_boundary(self, boundary):
        # Add a boundary to the model
        self.boundaries.append(boundary)

    def solve_ode(self,
                  time_int,
                  initial_concentrations,
                  sim_type = 'QSSA',
                  solver_type = 'vode',
                  reltol = 1e-8,
                  abstol = 1e-8):

        # Create the ode_fun if modified or non exisitent
        if self._modifed and not(hasattr(self,'ode_fun')):
            self.ode_fun = self.make_ode_fun(sim_type)
            self._modifed = False

        # Choose a solver
        self.solver = get_ode_solver(self.ode_fun,solver_type,reltol,abstol)

        # solve the ode
        t_sol,y_sol = solve_ode(self.solver,time_int,initial_concentrations)

        return Solution(self,t_sol,y_sol)

    def make_ode_fun(self, sim_type):

        # Gete all variables and expressions (Better solution with types?)
        if sim_type == 'QSSA':
            all_data = [this_reaction.mechanism.get_qssa_rate_expression()  \
                        for this_reaction in self.reactions.values()]

        elif sim_type == 'tQSSA':
            raise(NotImplementedError)
            all_data = [this_reaction.mechanism.get_tqssa_rate_expression() \
                        for this_reaction in self.reactions.values()]

        elif sim_type == 'full':
            all_data = [this_reaction.mechanism.get_full_rate_expression()  \
                        for this_reaction in self.reactions.values()]

        all_expr, all_param = list(zip(*all_data))

        # Flatten all the lists
        flatten_list = lambda this_list: [item for sublist in this_list \
                                          for item in sublist]

        all_rates = flatten_list([these_expressions.keys()
                                  for these_expressions in all_expr])
        all_param = join_dicts(all_param)

        # Get unique set of all the variables
        variables = list(set(all_rates))

        expr = dict.fromkeys(variables, 0.0)

        # Mass balance
        # Sum up all rate expressions
        for this_reaction in all_expr:
            for this_variable_key in this_reaction:
                expr[this_variable_key] += this_reaction[this_variable_key]

        # Apply boundary conditions. Boundaries are objects that act on
        # expressions
        for this_boundary in self.boundaries:
            this_boundary(expr)

        # Make vector function from expressions
        return ODEFunction(variables, expr, all_param)


def get_ode_solver(  ode_fun,
                     solver_type = "vode",
                     reltol = 1e-8,
                     abstol = 1e-8):

    # Initialize the integrator
    ode_solver = ode(ode_fun)
    # Set properties
    ode_solver.set_integrator(  solver_type,
                                method='bdf',
                                atol=abstol,
                                rtol=reltol )

    return ode_solver

def solve_ode(solver,time_int,initial_concentrations):

    solver.set_initial_value(initial_concentrations, time_int[0])

    t_sol = [time_int[0]]
    y_sol = [initial_concentrations]

    while solver.t <= time_int[1] and solver.successful():
            solver.integrate(time_int[1], step=True)
            t_sol.append(solver.t)
            y_sol.append(solver.y)

    return t_sol,y_sol