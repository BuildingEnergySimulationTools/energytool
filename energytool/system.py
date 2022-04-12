

class GazBoiler:
    def __init__(self, name, cop=0.86, energy="gaz", cost=0):
        self.name = name
        self.cop = cop
        self.energy = energy
        self.cost = cost

    def _pre_process(self, idf):
        return None

    def _post_process(self, eplus_res, zone_list):

