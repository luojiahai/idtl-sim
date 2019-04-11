from io import StringIO
import skbio
import skbio.tree

import numpy as np
import collections
import copy
from statistics import mean
import os
import pprint


count = 0
def increment():
    global count
    count += 1
    return count


class Debug(object):
    log_file = None
    event_count = {'d': 0, 'l': 0, 't': 0, 'i': 0}

    def __init__(self):
        pass

    @staticmethod
    def subtree_file_name(path, event, node_id, distance):
        return '{}/subtree_{}_{:03d}_{:07d}.txt'.format(path, event, node_id, int(distance * 10000))

    @staticmethod
    def save_tree_nodes(nodes, path, mode='w', distance=None):
        f = open(path, mode)
        if (distance): f.write(str(distance) + '\n')
        f.write('id\tname\tparent\td2p\n')
        for node in nodes:
            f.write(str(node.node_id) + '\t' + node.name + '\t' + str(node.parent) + '\t' + str(node.distance_to_parent) + '\n')
        f.close()

    @staticmethod
    def save_output(contents, path, mode='w'):
        f = open(path, mode)
        for content in contents:
            f.write(str(content))
            f.write('\n')
        f.close()

    @staticmethod
    def log(header, bodies=[], pformat=False):
        Debug.log_file.write(header)
        for body in bodies:
            if (pformat):
                Debug.log_file.write(pprint.pformat(body))
            else:
                Debug.log_file.write(str(body))
            Debug.log_file.write('\n')


class TreeNode(object):
    def __init__(self,
                 node_id=None,
                 name=None,
                 parent=None,
                 distance_to_parent=None,
                 children=None):
        self.node_id = node_id
        self.name = name
        self.parent = parent
        self.distance_to_parent = distance_to_parent
        self.children = children if children else []
        self.distance_to_children = []
        self.clade = []
        self.clade_split = []
        return
    
    def __repr__(self):
        return "node_id: {}, name: {}, parent: {}, distance_to_parent: {}, children: {}, distance_to_children: {}, clade: {}, clade_split: {}".format(
                self.node_id, 
                self.name,
                self.parent, 
                self.distance_to_parent,
                self.children,
                self.distance_to_children,
                self.clade,
                self.clade_split)


class GenericTree(object):
    def __init__(self):
        self.skbio_tree = None
        self.nodes = []
        self.root = None
        self.leaves = []
        self.nodes_id_dict = {}
        self.nodes_name_dict = {}
        self.total_distance = -1
        return

    def newick_to_table(self, output_path, input_path=None, skbio_tree=None):
        tree = None
        if (skbio_tree):
            tree = skbio_tree
        else:
            f = open(input_path)
            tree = skbio.read(f, format="newick", into=skbio.tree.TreeNode)
            f.close()

        def _parse(tree):
            node = {
                'object': tree,
                'name': tree.name,
                'parent': tree.parent,
                'children': [],
                'distance': tree.length
            }
            if tree.is_tip():
                return node
            for children in tree.children:
                node['children'].append(_parse(children))
            return node

        def _rename(node):
            ret = node.copy()
            name = ''
            for i in range(len(ret['children'])):
                ret['children'][i] = _rename(ret['children'][i])
                name += ret['children'][i]['name']
            if (not ret['name']):
                ret['name'] = name
            return ret

        def _to_list(node, root):
            d = node.copy()
            ret = []
            for i in range(len(d['children'])):
                ret += _to_list(d['children'][i], root=root)
            del d['children']
            d['distance_to_root'] = d['object'].distance(root)
            ret.append(d)
            if (d['object'] is root):
                ret = sorted(ret, key=lambda x: x['distance_to_root'], reverse=True)
            return ret

        root = _parse(tree)
        root = _rename(root)
        nodes = _to_list(root, root=root['object'])

        # output to file
        f = open(output_path, 'w')
        f.write('id\tname\tparent\td2p\n')
        for i in range(len(nodes)):
            parent_index = 'None'
            for j in range(len(nodes)):
                if (nodes[i]['parent'] is nodes[j]['object']):
                    parent_index = str(j)
            f.write(str(i) + '\t' + nodes[i]['name'] + '\t' + parent_index + '\t' + str(nodes[i]['distance']) + '\n')
        f.close()

        return tree

    def process_tree_recurse(self, tree):
        if (tree.name):
            return tree.name
        else:
            name = ''
            for child in tree.children:
                name += self.process_tree_recurse(child)
            tree.name = name
            return tree.name
    
    def construct_nodes(self, path, process_tree=False):
        # open table file and construct tree nodes
        f = open(path, 'r')
        f.readline()
        for line in f:
            splited = line.strip().split('\t')
            node_id = int(splited[0])
            name = splited[1]
            parent = splited[2]
            if (parent == 'None'):
                parent = -1
            d2p = splited[3]
            if (d2p == 'None'):
                d2p = -1.0
            self.nodes.append(TreeNode(node_id=node_id,
                                       name=name,
                                       parent=int(parent),
                                       distance_to_parent=float(d2p)))
        # process tree
        if (process_tree):
            self.process_tree_recurse(self.skbio_tree)
        # create dict
        for node in self.nodes:
            self.nodes_name_dict[node.name] = node
        # find children
        for node in self.nodes:
            children, node.distance_to_children = self.children_distances(self.skbio_tree, node.name)
            for child in children:
                node_id = self.nodes_name_dict[child.name].node_id
                node.children.append(node_id)
        return

    def children_distances_recurse(self, tree, name):
        ret = None
        if (tree.name == name):
            distances = []
            for child in tree.children:
                distances.append(tree.distance(child))
            ret = (tree.children, distances)
            return ret
        else:
            for child in tree.children:
                ret = self.children_distances_recurse(child, name)
                if (ret): return ret

    def children_distances(self, tree, name):
        return self.children_distances_recurse(tree, name)

    def node_by_id(self, node_id):
        return self.nodes_id_dict[node_id]

    def node_by_name(self, name):
        return self.nodes_name_dict[name]
    
    # find the distance of a given node to the root
    # needed when finding the walking distance
    def distance_to_root_recurse(self, node_id):        
        if (self.nodes_id_dict[node_id].parent < 0 or 
            node_id == self.root.node_id):
            return 0
        else:
            d2p = self.nodes_id_dict[node_id].distance_to_parent
            parent = self.nodes_id_dict[node_id].parent
            return d2p + self.distance_to_root_recurse(parent)

    # given a coalescent event happening at "branch_distance" above a speices node with "node_id"
    # find the distance of this event to the bottom of the tree
    # needed when assigning ids to the coalescent tree
    def distance_to_leaf(self, node_id, branch_distance):
        return branch_distance + (self.total_distance - self.distance_to_root_recurse(node_id))
        

class SpeciesTree(GenericTree):
    # static properties
    global_species_tree = None
    lambda_coal = None

    def __init__(self,
                 newick_path=None,
                 nodes=None):
        GenericTree.__init__(self)
        if (not newick_path):
            self.nodes = nodes
        else:
            self.construct_species_nodes(newick_path)

        max_node_id = -1
        for node in self.nodes:
            if (node.node_id > max_node_id):
                max_node_id = node.node_id
                self.root = node
            self.nodes_id_dict[node.node_id] = node
            self.nodes_name_dict[node.name] = node

            node.clade = []
            for i in range(len(node.name)):  
                char = node.name[i]
                node_id = self.node_by_name(char).node_id
                node.clade.append(node_id)

            node.clade_split = []
            if (node.children and not node.clade_split):
                for i in range(len(node.children)):
                    node_name = self.node_by_id(node.children[i]).name
                    split = []
                    for j in range(len(node_name)):  
                        char = node_name[j]
                        node_id = self.node_by_name(char).node_id
                        split.append(node_id)
                    node.clade_split.append(split)

        self.leaves = [node.node_id for node in self.nodes if not node.children]
        self.total_distance = self.distance_to_root_recurse(node_id=self.leaves[0])
        return

    def construct_species_nodes(self, newick_path):
        output_path = 'output/temp_species_nodes_table.txt'
        self.skbio_tree = super().newick_to_table(input_path=newick_path, output_path=output_path)
        super().construct_nodes(path=output_path, process_tree=True)
        return

    def get_lambda_coal(self, clade_set):
        indices = []
        for clade in clade_set:
            splited = clade.split('*')[:-1]
            for index in splited:
                indices.append(int(index))
        return mean(SpeciesTree.lambda_coal[indices])

    # checking whether a given clade is in the target set
    # modified for the "*" representation
    def star_in_set(self, target, clade):
        if (len(target) <= len(clade)):
            splited_target = target.split('*')[:-1]
            splited_clade = clade.split('*')[:-1]
            return set(splited_target).issubset(set(splited_clade))
        else:
            return False

    def star_sorted(self, couple):
        string = ''
        for e in couple:
            string += e
        splited = string.split('*')[:-1]
        splited = sorted([int(e) for e in splited])
        return [str(e) + '*' for e in splited]

    # This is the recursive part of the multi-species coalescent process:
    # Given a set of n genes gathering into a branch in the species tree from the bottom,
    #   whenever we come across a point of coalescence, we randomly merge 2 elements in the gene sets,
    #   and record the set before the new coalescence, named "from_set", and the set after the coalescence,
    #   named "to_set", and the distance from the last coalescent event or the bottom of the branch.
    def coalescent_recurse(self, node_id, distance, clade_set, coalescent_process):
        if (len(clade_set[node_id]) <= 1):
            return clade_set[node_id]
        else:
            lambda_c = len(clade_set[node_id]) * self.get_lambda_coal(clade_set[node_id])    # rate of coalescence
            distance_fake = np.random.exponential(scale=1.0/lambda_c)
            if (distance < distance_fake):      # no coalescent event anymore in this branch
                return clade_set[node_id]
            else:
                if (len(clade_set[node_id]) >= 2):   # when coalescent, randomly merge 2 elements in the gene sets
                    temp_set = sorted(clade_set[node_id])
                    couple = np.random.choice(clade_set[node_id], size=2, replace=False)
                    clade_set[node_id] = [''.join(self.star_sorted(couple))] + [e for e in clade_set[node_id] if e not in couple]

                    # print process
                    Debug.log(header="initial node " + str(node_id) + ": " + str(temp_set) + '\n')
                    Debug.log(header="coalescent at node " + str(node_id) + ": " + str(clade_set[node_id]) + ", " + "distance = " + str(distance_fake) + '\n')

                    # save process
                    coalescent_process[str(node_id)].append({
                        'from_set': temp_set, 
                        'to_set': clade_set[node_id].copy(),
                        'distance': distance_fake
                    })
                else:
                    return clade_set[node_id]     # stop when gene set only has one single element
                distance = distance - distance_fake
                self.coalescent_recurse(node_id=node_id, 
                                        distance=distance, 
                                        clade_set=clade_set,
                                        coalescent_process=coalescent_process)     # use recursion to simulate the case when there is more than one coalescent events in the branch
        return clade_set[node_id]

    # the main multi-species coalecent function
    def coalescent(self, distance_above_root):
        nodes = self.nodes
        root = self.root
        coalescent_process = collections.defaultdict(list)
        clade_set_into_root = None

        old_leaves = [node.node_id for node in nodes if not node.children]      # leaves of the given species tree
        new_leaves = []     # leaves set will be updated in the loop
        clade_set = {}      # set of extant species that an ancestral gene will finally be fixed in
        labelled = {}       # avoid doing repeated coalescence
        for node in nodes:
            labelled[node.node_id] = False
            clade_set[node.node_id] = [str(node.node_id) + '*'] if not node.children else []

        while (True):
            for leaf in old_leaves:
                if (leaf == root.node_id):
                    clade_set_into_root = self.coalescent_recurse(node_id=root.node_id, 
                                            distance=distance_above_root, 
                                            clade_set=clade_set,
                                            coalescent_process=coalescent_process)
                    break
                else:
                    parent = self.nodes_id_dict[leaf].parent
                    children = self.nodes_id_dict[parent].children
                    if (labelled[leaf]):
                        continue
                    labelled[leaf] = True
                    if (len(clade_set[children[0]]) != 0 
                        and len(clade_set[children[1]]) != 0):
                        self.coalescent_recurse(node_id=children[0], 
                                                distance=self.nodes_id_dict[children[0]].distance_to_parent,
                                                clade_set=clade_set,
                                                coalescent_process=coalescent_process)
                        self.coalescent_recurse(node_id=children[1], 
                                                distance=self.nodes_id_dict[children[1]].distance_to_parent,
                                                clade_set=clade_set,
                                                coalescent_process=coalescent_process)
                        # the clade set of the parent before coalescence is the union of the clade set of its children after coalescence                        
                        clade_set[parent] = list(set().union(clade_set[children[0]], clade_set[children[1]]))    
                        if (len(new_leaves) > 0):
                            new_leaves = [e for e in new_leaves if e != children[0] and e != children[1]]
                        new_leaves.append(parent)
                    else:
                        new_leaves.append(leaf)     # updating leaves set
            if (leaf == root.node_id):
                break
            temp_new_leaves = []
            for new_leaf in new_leaves:
                if (new_leaf not in temp_new_leaves):
                    temp_new_leaves.append(new_leaf)
            old_leaves = temp_new_leaves.copy()
            new_leaves = []
            labelled = {}
            for node in nodes:
                labelled[node.node_id] = False
        return coalescent_process, clade_set_into_root

    # this is the main function of doing sub_species-tree coalescence
    # this will be used when modelling duplications and transfers
    # Given a sub_species_tree, and a subset of leaves in the sub_species_tree, named "sub_leaves"
    #   this function dose a multi-species coalescence based on the sub_species-tree only considering the sub_leaves
    def sub_leaves_coalescent(self, distance_above_root, sub_leaves):
        nodes = self.nodes
        root = self.root
        coalescent_process = collections.defaultdict(list)

        old_leaves = [node.node_id for node in nodes if not node.children]
        new_leaves = []
        clade_set = {}
        labelled = {}
        mark = {} 

        for node in nodes:
            mark[node.node_id] = True
            labelled[node.node_id] = False
            clade_set[node.node_id] = [str(node.node_id) + '*'] if not node.children else [] 
        for leaf in old_leaves: mark[leaf] = False
        for leaf in sub_leaves: mark[leaf] = True       # mark the leaves of the sub_species_tree but not in the sub_leaves set as FALSE

        while (True):
            for leaf in old_leaves:
                if (leaf == root.node_id):
                    self.coalescent_recurse(node_id=root.node_id, 
                                            distance=distance_above_root, 
                                            clade_set=clade_set,
                                            coalescent_process=coalescent_process)
                    if len(clade_set[root.node_id]) == 1: break
                    else: return self.sub_leaves_coalescent(distance_above_root, sub_leaves)
                else:
                    parent = self.nodes_id_dict[leaf].parent
                    children = self.nodes_id_dict[parent].children
                    if (labelled[leaf]):
                        continue
                    labelled[leaf] = True
                    if (len(clade_set[children[0]]) != 0 
                        and len(clade_set[children[1]]) != 0):
                            if (mark[children[0]] and mark[children[1]]):       # when both children are marked, do normal coalescence
                                self.coalescent_recurse(node_id=children[0], 
                                                        distance=self.nodes_id_dict[children[0]].distance_to_parent,
                                                        clade_set=clade_set,
                                                        coalescent_process=coalescent_process)
                                self.coalescent_recurse(node_id=children[1], 
                                                        distance=self.nodes_id_dict[children[1]].distance_to_parent,
                                                        clade_set=clade_set,
                                                        coalescent_process=coalescent_process)
                                clade_set[parent] = list(set().union(clade_set[children[0]], clade_set[children[1]]))
                                if (len(new_leaves) > 0):
                                    new_leaves = [e for e in new_leaves if e != children[0] and e != children[1]]
                                new_leaves.append(parent)
                            elif not (mark[children[0]] or mark[children[1]]):      # when neither childer is marked, we mark the parent as FALSE
                                mark[parent] = False
                                clade_set[parent] = "$"
                                if (len(new_leaves) > 0):
                                    new_leaves = [e for e in new_leaves if e != children[0] and e != children[1]]
                                new_leaves.append(parent)
                            elif (mark[children[0]]):       # when only one child is marked, let the clade set of the unmarked child be empty
                                clade_set[parent] = clade_set[children[0]]
                                if (len(new_leaves) > 0):
                                    new_leaves = [e for e in new_leaves if e != children[0] and e != children[1]]
                                new_leaves.append(parent)
                            elif (mark[children[1]]):
                                clade_set[parent] = clade_set[children[1]]
                                if (len(new_leaves) > 0):
                                    new_leaves = [e for e in new_leaves if e != children[0] and e != children[1]]
                                new_leaves.append(parent)
                    else:
                        new_leaves.append(leaf)
            if (leaf == root.node_id):
                break
            temp_new_leaves = []
            for new_leaf in new_leaves:
                if (new_leaf not in temp_new_leaves):
                    temp_new_leaves.append(new_leaf)
            old_leaves = temp_new_leaves.copy()
            new_leaves = []
            labelled = {}
            for node in nodes:
                labelled[node.node_id] = False
        return coalescent_process

    def incomplete_coalescent(self, distance_above_root):
        full_coal_process, genes_into_root = self.coalescent(distance_above_root=10000)
        chosen_gene = np.random.choice(genes_into_root)
        sub_coal_process = self.filter_coal_process(full_coal_process, chosen_gene)
        return sub_coal_process, chosen_gene

    def bounded_coalescent(self, distance_above_root):
        coal_process, genes_into_root = self.coalescent(distance_above_root)
        if (len(genes_into_root) == 1):
            return coal_process
        else:
            return self.bounded_coalescent(distance_above_root)

    # given a coalescent process obtained by incomplete coalescent,
    # one may have more than one subtrees in the full_coal_process,
    # we can choose a subtree rooted at the chosen_gene,
    # at this stage, the subtree is represented as a modified coal_process.
    def filter_coal_process(self, full_coal_process, chosen_gene):
        coal_process = collections.defaultdict(list)
        for k, v in full_coal_process.items():
            for elem in v:
                distance = elem['distance']
                from_set = []
                to_set = []
                for clade in elem['from_set']:
                    if (self.star_in_set(target=clade, clade=chosen_gene)):
                        from_set.append(clade)
                for clade in elem['to_set']:
                    if (self.star_in_set(target=clade, clade=chosen_gene)):
                        to_set.append(clade)
                if (to_set):
                    coal_process[k].append({
                        'from_set': from_set, 
                        'to_set': to_set,
                        'distance': distance
                    })
        return coal_process
    
    # find the ancestors of the given leaf in reverse time order
    def find_ancestors(self, leaf_name, coalescent_process):
        sequence = []
        for k, v in coalescent_process.items():
            branch_distance = 0.0
            for elem in v:
                branch_distance += elem['distance']
                if (leaf_name in elem['from_set'] and leaf_name not in elem['to_set']):
                    for e in elem['to_set']:
                        if len(leaf_name) < len(e) and self.star_in_set(leaf_name, e):
                            species_node_id = int(k)
                            species_node_height = super().distance_to_leaf(int(k), branch_distance=0)
                            coal_height = super().distance_to_leaf(int(k), branch_distance=branch_distance)
                            # pair = (ancestor, coal_height)
                            pair = (e, coal_height)
                            sequence.append(pair)
                            sequence += self.find_ancestors(leaf_name=e, 
                                                                coalescent_process=coalescent_process)
        return sequence

    # backward-in-time coalescent process
    # modified data structure for constructing the coalescent tree in newick format
    def time_sequences(self, coalescent_process):
        time_sequences = {}
        for leaf in self.leaves:
            time_sequences[str(leaf)] = self.find_ancestors(leaf_name=str(leaf)+'*', 
                                                                coalescent_process=coalescent_process)
        return time_sequences


class GeneTree(GenericTree):
    # static properties
    dup_recombination = 0
    trans_hemiplasy = 0
    lambda_dup = None
    lambda_loss = None
    lambda_trans = None

    def __init__(self,
                 time_sequences,
                 species_tree):
        GenericTree.__init__(self)
        self.time_sequences = time_sequences
        self.construct_gene_nodes()

        max_node_id = -1
        for node in self.nodes:
            if (node.node_id > max_node_id):
                max_node_id = node.node_id
                self.root = node
            self.nodes_id_dict[node.node_id] = node
            self.nodes_name_dict[node.name] = node

        for node in self.nodes:
            clade = node.name.split('*')[:-1]
            clade = [int(j) for j in clade]
            node.clade = clade
            if (node.children and not node.clade_split):
                for i in range(len(node.children)):
                    node_name = self.node_by_id(node.children[i]).name 
                    clade = node_name.split('*')[:-1]
                    clade = [int(j) for j in clade]
                    node.clade_split.append(clade)
    
        self.species_tree = species_tree
        self.leaves = [node.node_id for node in self.nodes if not node.children]
        self.total_distance = self.distance_to_root_recurse(node_id=self.leaves[0])
        return

    # string replacement modified for the "*" representation
    def star_replace(self, string, substring):
        a = string.split('*')[:-1]
        b = substring.split('*')[:-1]
        diff = set(a).difference(set(b))
        return ''.join([e + '*' for e in sorted(list(diff))])

    def distance_from_to(self, node_name, parent_name):
        for leaf, sequence in self.time_sequences.items():
            if (node_name.count('*') == 1 and node_name[0] == leaf):
                for pair in sequence:
                    if (pair[0] == parent_name):
                        return pair[1]
            else:
                prev_pair = None
                for pair in sequence:
                    if (prev_pair != None and prev_pair[0] == node_name and pair[0] == parent_name):
                        return pair[1] - prev_pair[1]
                    prev_pair = pair
        return None

    def create_skbio_tree_recurse(self, skbio_tree_node):
        # one node (leaf)
        if (skbio_tree_node.name.count('*') == 1):
            skbio_tree_node.length = self.distance_from_to(skbio_tree_node.name, skbio_tree_node.parent.name)
            return
        # two nodes
        elif (len(skbio_tree_node.name) == 4):
            child_one_name = skbio_tree_node.name[:2]
            child_two_name = skbio_tree_node.name[2:]
            child_one = skbio.tree.TreeNode(name=child_one_name, 
                                            length=self.distance_from_to(child_one_name, skbio_tree_node.name), 
                                            parent=skbio_tree_node)
            child_two = skbio.tree.TreeNode(name=child_two_name, 
                                            length=self.distance_from_to(child_two_name, skbio_tree_node.name),
                                            parent=skbio_tree_node)
            skbio_tree_node.children = [child_one, child_two]
            return
        is_found = False
        for leaf, sequence in self.time_sequences.items():
            prev_pair = None
            for pair in sequence:
                if (prev_pair != None and skbio_tree_node.name == pair[0]):
                    child_one_name = prev_pair[0]
                    child_two_name = self.star_replace(skbio_tree_node.name, prev_pair[0])
                    child_one = skbio.tree.TreeNode(name=child_one_name, 
                                                    length=self.distance_from_to(child_one_name, skbio_tree_node.name), 
                                                    parent=skbio_tree_node)
                    child_two = skbio.tree.TreeNode(name=child_two_name, 
                                                    length=self.distance_from_to(child_two_name, skbio_tree_node.name),
                                                    parent=skbio_tree_node)
                    self.create_skbio_tree_recurse(child_one)
                    self.create_skbio_tree_recurse(child_two)
                    skbio_tree_node.children = [child_one, child_two]
                    is_found = True
                    break
                prev_pair = pair
            if (is_found):
                break
        return

    # construct ghe gene tree in newick format from time sequence
    def construct_gene_nodes(self):
        tree = skbio.tree.TreeNode() # empty tree, initialization
        time_seq = self.time_sequences.copy()
        for k, v in self.time_sequences.items():
            if (not v): del time_seq[k]
        if (len(time_seq) > 0 and next(iter(time_seq.values()))):
            tree.name = next(iter(time_seq.values()))[-1][0]
            self.create_skbio_tree_recurse(tree)
            tree.length = None
            self.skbio_tree = tree
            output_path = 'output/temp_gene_nodes_table.txt'
            super().newick_to_table(skbio_tree=tree, output_path=output_path)
            super().construct_nodes(path=output_path, process_tree=False)   
        else: 
            tree.name = next(iter(self.time_sequences)) + '*' # empty
            tree.length = None
            self.skbio_tree = tree

            self.nodes.append(TreeNode(node_id=0,
                                       name=tree.name,
                                       parent=-1,
                                       distance_to_parent=-1.0))
        return

    def get_lambda_dup(self, clade):
            indices = []
            splited = clade.split('*')[:-1]
            for index in splited:
                indices.append(int(index))
            return mean(GeneTree.lambda_dup[indices])

    def get_lambda_loss(self, clade):
            indices = []
            splited = clade.split('*')[:-1]
            for index in splited:
                indices.append(int(index))
            return mean(GeneTree.lambda_loss[indices])

    def get_lambda_trans(self, clade):
            indices = []
            splited = clade.split('*')[:-1]
            for index in splited:
                indices.append(int(index))
            return mean(GeneTree.lambda_trans[indices])

    def find_trans_target(self, event_height, node_id):
        tree = SpeciesTree.global_species_tree
        species_nodes = tree.nodes
        nodes_list = []
        for node in species_nodes:
            if (node.node_id == node_id):
                continue
            if (node.node_id == tree.root.node_id):
                continue
            parent_height = tree.distance_to_leaf(tree.node_by_id(node.parent).node_id, 0)
            if (parent_height > event_height):
                node_height = tree.distance_to_leaf(node.node_id, 0)
                if (node_height <= event_height):
                    nodes_list.append(node.node_id)
        return np.random.choice(nodes_list)

    # find the points of duplicatons and losses recursively
    def dlt_process_recurse(self, tree, distance, events):
        node = self.nodes_name_dict[tree.name]
        distance_dup = np.random.exponential(scale=1.0/self.get_lambda_dup(node.name))
        distance_loss = np.random.exponential(scale=1.0/self.get_lambda_loss(node.name))
        distance_trans = np.random.exponential(scale=1.0/self.get_lambda_trans(node.name))
        if (distance_dup < min(distance_loss, distance_trans) and distance_dup < distance):      # duplication happens first
            Debug.log(header='duplication at node ' + str(node.node_id) + ' (' + node.name + ')' + ' with distance ' + str(distance - distance_dup) + '\n')
            event_height = super().distance_to_leaf(node.node_id, 0) + distance - distance_dup
            events.append({
                'type': 'duplication',
                'node_id': node.node_id, 
                'name': node.name, 
                'distance': distance - distance_dup,
                'event_height': event_height
            })
            self.dt_process_recurse(tree, distance - distance_dup, events) # looking for more events on the same branch
        elif (distance_trans <= min(distance_dup, distance_loss) and distance_trans < distance):
            event_height = super().distance_to_leaf(node.node_id, 0) + distance - distance_trans
            species_tree_height = SpeciesTree.global_species_tree.total_distance
            if (event_height < species_tree_height):
                Debug.log(header='transfer at node ' + str(node.node_id) + ' (' + node.name + ')' + ' with distance ' + str(distance - distance_trans) + '\n')
                target = self.find_trans_target(event_height, node.node_id)
                events.append({
                    'type': 'transfer',
                    'node_id': node.node_id, 
                    'name': node.name, 
                    'distance': distance - distance_trans,
                    'target': target,
                    'event_height': event_height
                })
            self.dt_process_recurse(tree, distance - distance_trans, events)
        elif (distance_loss <= min(distance_dup, distance_trans) and distance_loss < distance):      # loss happens first, the seaching process stops at the loss point
            Debug.log(header='loss at node ' + str(node.node_id) + ' (' + node.name + ')' + ' with distance ' + str(distance - distance_loss) + '\n')
            events.append({
                'type': 'loss',
                'node_id': node.node_id, 
                'name': node.name, 
                'distance': distance - distance_loss,
                'sub_tree_root_name': tree.name
            })
        else:   # reach the end the current branch, looking for events in the 2 children branches
            Debug.log(header='nothing happened at node ' + str(node.node_id) + ' (' + node.name + ')' + '\n')
            if (node.children):     # if children branches exist
                child_one = tree.children[0]
                child_two = tree.children[1]
                distance_to_child_one = node.distance_to_children[0]
                distance_to_child_two = node.distance_to_children[1]
                self.dt_process_recurse(child_one, distance_to_child_one, events)
                self.dt_process_recurse(child_two, distance_to_child_two, events)
            else:       # if not exist, reach the leaves of the tree, searching process stops
                Debug.log(header='reach the end of node ' + str(node.node_id) + ' (' + node.name + ')' + '\n')
        return

    # find the points of duplicatons and losses recursively
    def dt_process_recurse(self, tree, distance, events):
        node = self.nodes_name_dict[tree.name]
        distance_dup = np.random.exponential(scale=1.0/self.get_lambda_dup(node.name))
        distance_loss = 10000
        distance_trans = np.random.exponential(scale=1.0/self.get_lambda_trans(node.name))
        if (distance_dup < min(distance_loss, distance_trans) and distance_dup < distance):      # duplication happens first
            Debug.log(header='duplication at node ' + str(node.node_id) + ' (' + node.name + ')' + ' with distance ' + str(distance - distance_dup) + '\n')
            event_height = event_height = super().distance_to_leaf(node.node_id, 0) + distance - distance_dup
            events.append({
                'type': 'duplication',
                'node_id': node.node_id, 
                'name': node.name, 
                'distance': distance - distance_dup,
                'event_height': event_height
            })
            self.dt_process_recurse(tree, distance - distance_dup, events) # looking for more events on the same branch
        elif (distance_trans <= min(distance_dup, distance_loss) and distance_trans < distance):
            event_height = super().distance_to_leaf(node.node_id, 0) + distance - distance_trans
            species_tree_height = SpeciesTree.global_species_tree.total_distance
            if (event_height < species_tree_height):
                Debug.log(header='transfer at node ' + str(node.node_id) + ' (' + node.name + ')' + ' with distance ' + str(distance - distance_trans) + '\n')
                target = self.find_trans_target(event_height, node.node_id)
                events.append({
                    'type': 'transfer',
                    'node_id': node.node_id, 
                    'name': node.name, 
                    'distance': distance - distance_trans,
                    'target': target,
                    'event_height': event_height
                })
            self.dlt_process_recurse(tree, distance - distance_trans, events)
        elif (distance_loss <= min(distance_dup, distance_trans) and distance_loss < distance):      # loss happens first, the seaching process stops at the loss point
            Debug.log(header='loss at node ' + str(node.node_id) + ' (' + node.name + ')' + ' with distance ' + str(distance - distance_loss) + '\n')
            events.append({
                'type': 'loss',
                'node_id': node.node_id, 
                'name': node.name, 
                'distance': distance - distance_loss,
                'sub_tree_root_name': tree.name
            })
        else:   # reach the end the current branch, looking for events in the 2 children branches
            Debug.log(header='nothing happened at node ' + str(node.node_id) + ' (' + node.name + ')' + '\n')
            if (node.children):     # if children branches exist
                child_one = tree.children[0]
                child_two = tree.children[1]
                distance_to_child_one = node.distance_to_children[0]
                distance_to_child_two = node.distance_to_children[1]
                self.dlt_process_recurse(child_one, distance_to_child_one, events)
                self.dlt_process_recurse(child_two, distance_to_child_two, events)
            else:       # if not exist, reach the leaves of the tree, searching process stops
                Debug.log(header='reach the end of node ' + str(node.node_id) + ' (' + node.name + ')' + '\n')
        return
    
    # store the duplication events
    def dlt_process(self, distance, event=None):
        events = []

        if (len(self.nodes) == 1):
            distance = event['distance']
        self.dlt_process_recurse(self.skbio_tree, 
                                    distance=distance, 
                                    events=events)  
        return events
    
    def find_ils(self, path):
        for i in range(len(self.nodes)):
            j = len(self.nodes)-1-i
            gene_node = self.node_by_id(j)
            gene_clade = gene_node.clade
            gene_splits = gene_node.clade_split
            find_species_node = False
            for node in self.species_tree.nodes:
                if (node.clade == gene_clade):
                    find_species_node = True
                    species_node = node
                    break
            if not find_species_node:
                continue
            species_clade = species_node.clade
            species_splits = species_node.clade_split
            find_ils = False
            if (gene_splits):
                gene_split_0 = set(gene_splits[0])
                gene_split_1 = set(gene_splits[1])
                for species_split in species_splits:
                    if (set(species_split).intersection(gene_split_0) and set(species_split).intersection(gene_split_1)):
                        find_ils = True
                        break
            if (find_ils):
                Debug.event_count['i'] += 1
                file_name = 'ils_' + str(Debug.event_count['i'])
                f = open(os.path.join(path, file_name), 'w')
                f.write(str(gene_node.name) + ',' + str(gene_split_0) + ' ' + str(gene_split_1))
                f.close()
                print('find ils at gene node ' + str(gene_node.name) + ' split: ' + str(gene_split_0) + ' ' + str(gene_split_1))

    # find the duplication subtree and do subtree coalescence
    def dt_subtree_recurse(self, event, node_id, coal_distance, path):

        if (event['type'] == 'transfer'): # node_id = target_id
            Debug.log(header='\n\n\n' + '='*80 + '\nCurrent event:' + '\n',
                      bodies=[event], pformat=True)
            tree = SpeciesTree.global_species_tree
            species_skbio_tree = tree.skbio_tree
            name = tree.nodes_id_dict[node_id].name

            subtree = species_skbio_tree.find(name).deepcopy()
            subtree_names = [node.name for node in subtree.traverse()]
            subtree_nodes = [node for node in tree.nodes if node.name in subtree_names]
            species_subtree = SpeciesTree(nodes=subtree_nodes)
            species_subtree.skbio_tree = subtree
            Debug.log(header='\nspecies_subtree_nodes:\n', bodies=species_subtree.nodes)

            distance_above_root = coal_distance
            Debug.log(header='\nspecies_subtree_coal:\n')
            if (GeneTree.trans_hemiplasy == 1):
                species_subtree_coal_process, chosen_gene = species_subtree.incomplete_coalescent(distance_above_root)
            elif (GeneTree.trans_hemiplasy == 0):
                species_subtree_coal_process = species_subtree.bounded_coalescent(distance_above_root=distance_above_root)

            Debug.log(header='\nspecies_subtree_coal_process:\n', 
                      bodies=[species_subtree_coal_process], pformat=True)

            species_subtree_time_seq = species_subtree.time_sequences(coalescent_process=species_subtree_coal_process)
            Debug.log(header='\nspecies_subtree_time_seq:' + '\n',
                      bodies=[species_subtree_time_seq], pformat=True)

            # save subtree
            Debug.save_tree_nodes(nodes=species_subtree.nodes, 
                                  path=Debug.subtree_file_name('output/subtrees', 'trans', node_id, distance_above_root), 
                                  distance=distance_above_root)
            
            gene_subtree = GeneTree(time_sequences=species_subtree_time_seq, species_tree=species_subtree)
            gene_subtree.skbio_tree.length = event['event_height'] - gene_subtree.total_distance
            Debug.log(header='\ngene_subtree nodes:\n', bodies=gene_subtree.nodes)
            Debug.save_tree_nodes(nodes=gene_subtree.nodes, 
                                  path=Debug.subtree_file_name('output/subtrees', 'trans', node_id, distance_above_root), 
                                  mode='a')

            Debug.save_output(contents=[gene_subtree.skbio_tree],
                              path=Debug.subtree_file_name('output/newick_gene_subtrees', 'trans', node_id, distance_above_root))

            Debug.log(header='\ngene_subtree dlt_process:\n')
            gene_subtree_height = gene_subtree.total_distance
            gene_subtree_events = gene_subtree.dlt_process(event=event, distance=event['event_height'] - gene_subtree_height)
            Debug.log(header='\ngene_subtree events:\n', bodies=[gene_subtree_events], pformat=True)
            
            _id = 'trans_subtree_' + str(increment())
            next_dir = os.path.join(path, _id)
            os.mkdir(next_dir)
            file_name = 'event.txt'
            f = open(os.path.join(next_dir, file_name), 'w')
            f.write(str(event['name']) + ',' + str(event['distance']) + ',' + str(event['type']))
            f.close()
            gene_subtree.dt_subtree(coalescent_process=species_subtree_coal_process, events=gene_subtree_events, path=next_dir)

        if (event['type'] == 'duplication'):
            Debug.log(header='\n\n\n' + '='*80 + '\nCurrent event:' + '\n',
                      bodies=[event], pformat=True)
            species_skbio_tree = self.species_tree.skbio_tree
            name = self.species_tree.nodes_id_dict[node_id].name

            subtree = species_skbio_tree.find(name).deepcopy()
            subtree_names = [node.name for node in subtree.traverse()]
            subtree_nodes = [node for node in self.species_tree.nodes if node.name in subtree_names]

            species_subtree = SpeciesTree(nodes=subtree_nodes)
            species_subtree.skbio_tree = subtree
            Debug.log(header='\nspecies_subtree_nodes:\n', bodies=species_subtree.nodes)

            distance_above_root = event['distance'] + coal_distance
            sub_leaves = [int(node_id) for node_id in event['name'].strip().split('*')[:-1]]
            Debug.log(header='\nspecies_subtree_coal:\n')
            if (GeneTree.dup_recombination == 0):
                species_subtree_coal_process, chosen_gene = species_subtree.incomplete_coalescent(distance_above_root)
            elif (GeneTree.dup_recombination == 1):
                species_subtree_coal_process = species_subtree.sub_leaves_coalescent(distance_above_root=distance_above_root, sub_leaves=sub_leaves)

            Debug.log(header='\nspecies_subtree_coal_process:\n',
                      bodies=[species_subtree_coal_process], pformat=True)

            species_subtree_time_seq = species_subtree.time_sequences(coalescent_process=species_subtree_coal_process)
            Debug.log(header='\nspecies_subtree_time_seq:\n',
                      bodies=[species_subtree_time_seq], pformat=True)

            # save subtree
            Debug.save_tree_nodes(nodes=species_subtree.nodes, 
                                  path=Debug.subtree_file_name('output/subtrees', 'dup', node_id, distance_above_root), 
                                  distance=distance_above_root)
            
            gene_subtree = GeneTree(time_sequences=species_subtree_time_seq, species_tree=species_subtree)
            gene_subtree.skbio_tree.length = event['event_height'] - gene_subtree.total_distance
            Debug.log(header='\ngene_subtree nodes:\n', bodies=gene_subtree.nodes)
            Debug.save_tree_nodes(nodes=gene_subtree.nodes, 
                                  path=Debug.subtree_file_name('output/subtrees', 'dup', node_id, distance_above_root), 
                                  mode='a')

            Debug.save_output(contents=[gene_subtree.skbio_tree],
                              path=Debug.subtree_file_name('output/newick_gene_subtrees', 'dup', node_id, distance_above_root))

            Debug.log(header='\ngene_subtree dlt_process:\n')
            gene_subtree_height = gene_subtree.total_distance
            gene_subtree_events = gene_subtree.dlt_process(event=event, distance=event['event_height'] - gene_subtree_height)
            Debug.log(header='\ngene_subtree events:\n',
                      bodies=[gene_subtree_events], pformat=True)

            _id = 'dup_subtree_' + str(increment())
            next_dir = os.path.join(path, _id)
            os.mkdir(next_dir)
            file_name = 'event.txt'
            f = open(os.path.join(next_dir, file_name), 'w')
            f.write(str(event['name']) + ',' + str(event['distance']) + ',' + str(event['type']))
            f.close()
            gene_subtree.dt_subtree(coalescent_process=species_subtree_coal_process, events=gene_subtree_events, path=next_dir)
        
        return

    # find all the duplication points on the coalescent tree
    # find the corresponding duplicaion subtree
    # do subtree coalescence to obtain the sub_coalescent_tree
    # find all the duplication points on the sub_coalescent_tree
    # recurse
    def dt_subtree(self, coalescent_process, events, path):
        if (path):
            f = open(os.path.join(path, 'gene_tree.txt'), 'w')
            f.write(str(self.skbio_tree))
            f.close()
            f = open(os.path.join(path, 'species_tree.txt'), 'w')
            f.write(str(self.species_tree.skbio_tree))
            f.close()
            self.find_ils(path)
        if (not events):
            return
        for event in events:
            if (event['type'] == 'duplication'):
                Debug.event_count['d'] += 1
                node_id = None
                coal_distance = None
                if (coalescent_process):        # non-trivial
                    for k, v in coalescent_process.items():
                        for elem in v:
                            if (event['name'] in elem['to_set'] and event['name'] not in elem['from_set']):
                                node_id = int(k)
                                coal_distance = elem['distance']
                    if (node_id == None):
                        node_id = int(event['name'][:-1])
                        coal_distance = 0
                    self.dt_subtree_recurse(event=event, node_id=node_id, coal_distance=coal_distance, path=path)
                else:       # trivial
                    node_id = int(event['name'][:-1])
                    coal_distance = 0
                    self.dt_subtree_recurse(event=event, node_id=node_id, coal_distance=coal_distance, path=path)
            elif (event['type'] == 'transfer'):
                Debug.event_count['t'] += 1
                trans_target_id = event['target']
                target_height = SpeciesTree.global_species_tree.distance_to_leaf(trans_target_id, 0)
                distance_above_target = event['event_height'] - target_height
                self.dt_subtree_recurse(event=event, node_id=trans_target_id, coal_distance=distance_above_target, path=path)
            elif (event['type'] == 'loss'):
                Debug.event_count['l'] += 1
                file_name = 'loss_' + str(event['distance'])
                f = open(os.path.join(path, file_name), 'w')
                f.write(str(event['name']) + ',' + str(event['distance']))
                f.close()
        return