from dataclasses import dataclass
from typing import List


@dataclass
class owned_blueprints_blueprints:
    id: int
    name: str
    owned_count: int
    base_cost: int

    def __init__(self):
        self.name = ""

    def class_string(self):
        return "table-success" if self.owned_count > 0 else "table-danger"


@dataclass
class owned_blueprints_market_groups:
    market_group_id: int
    market_group_name: str
    description: str
    blueprint_count: int
    owned_count: int
    sub_groups: list['owned_blueprints_market_groups']
    blueprints: list[owned_blueprints_blueprints]

    _calculated_blueprint_count: int = None
    _calculated_owned_count: int = None
    _calculated_base_cost: int = None

    def __init__(self):
        self.market_group_name = ""
        self.description = ""
        self.sub_groups = []
        self.blueprints = []
        self.owned_count = 0
        self.blueprint_count = 0

    def calculated_blueprint_count(self):
        if self._calculated_blueprint_count is None:
            self._calculated_blueprint_count = self.blueprint_count
            for sub_group in self.sub_groups:
                self._calculated_blueprint_count += sub_group.calculated_blueprint_count()
        return self._calculated_blueprint_count
    

    def calculated_owned_count(self):
        if self._calculated_owned_count is None:
            self._calculated_owned_count = self.owned_count
            for blueprint in self.blueprints:
                if blueprint.owned_count > 0:
                    self._calculated_owned_count += 1
            for sub_group in self.sub_groups:
                self._calculated_owned_count += sub_group.calculated_owned_count()
        return self._calculated_owned_count
    

    def calculated_base_cost(self):
        if self._calculated_base_cost is None:
            self._calculated_base_cost = 0
            for blueprint in self.blueprints:
                if blueprint.owned_count == 0:
                    self._calculated_base_cost += blueprint.base_cost
            for sub_group in self.sub_groups:
                self._calculated_base_cost += sub_group.calculated_base_cost()
        return self._calculated_base_cost
        

@dataclass
class owned_blueprints:
    market_groups: list[owned_blueprints_market_groups]

    def __init__(self):
        self.market_groups = []

    def all_costs(self):
        cost = 0
        for market_group in self.market_groups:
            cost += market_group.calculated_base_cost()
        return cost
    

    def all_owned(self):
        owned = 0
        for market_group in self.market_groups:
            owned += market_group.calculated_owned_count()
        return owned
    

    def all_total(self):
        total = 0
        for market_group in self.market_groups:
            total += market_group.calculated_blueprint_count()
        return total
    