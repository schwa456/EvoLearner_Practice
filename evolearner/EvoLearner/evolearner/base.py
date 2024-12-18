from collections import defaultdict
from owlready2 import Ontology, World, sync_reasoner_pellet
import owlready2
from .concept_generator import ConceptGenerator
from .concept import Concept
from typing import Dict, Tuple, Set, Generator, Iterable
import warnings

warnings.filterwarnings("ignore")


class KnowledgeBase:
    """Knowledge Base Class representing Tbox and
       Abox along with concept hierarchies"""

    def __init__(self, path,
                 min_size_of_concept=1,
                 max_concept_size_ratio=1.0,
                 use_pellet=False):
        self.path = path
        self.onto = World().get_ontology(self.path).load(reload=True)

        if use_pellet:
            with self.onto:
                sync_reasoner_pellet(x=self.onto.world,
                                     infer_property_values=True,
                                     infer_data_property_values=True)

        self.name = self.onto.name
        self.concepts = dict()
        self.thing = None
        self.nothing = None

        # Next time thing about including this into Concepts.
        self.top_down_concept_hierarchy = defaultdict(set)
        self.top_down_direct_concept_hierarchy = defaultdict(set)
        self.down_top_concept_hierarchy = defaultdict(set)
        self.down_top_direct_concept_hierarchy = defaultdict(set)
        self.concepts_to_leafs = defaultdict(set)
        self.property_hierarchy = None
        self.parse()

        self.min_size_of_concept = min_size_of_concept

        self.max_size_of_concept = len(self.thing.instances) * (
                                   max_concept_size_ratio)

        self.role_log = dict()
        self.role_log_cardinality = dict()
        self.__concept_generator = (
                ConceptGenerator(self, concepts=self.concepts,
                                 T=self.thing,
                                 Bottom=self.nothing,
                                 onto=self.onto,
                                 min_size_of_concept=self.min_size_of_concept,
                                 max_size_of_concept=self.max_size_of_concept))

    @staticmethod
    def apply_type_enrichment_from_iterable(concepts: Iterable[Concept],
                                            world):
        """
        Extend ABOX by
        (1) Obtaining all instances of selected concepts.
        (2) For all instances in (1) include type information into ABOX.
        @param concepts:
        @return:
        """
        for c in concepts:
            for ind in c.owl.instances(world=world):
                ind.is_a.append(c.owl)

    @staticmethod
    def apply_type_enrichment(concept: Concept):
        for ind in concept.instances:
            ind.is_a.append(concept.owl)

    def save(self, path, rdf_format='ntriples'):
        self.onto.save(file=path, format=rdf_format)

    def get_all_individuals(self) -> Set:
        return self.thing.instances

    def set_min_size_of_concept(self, n):
        self.min_size_of_concept = n

    @staticmethod
    def is_atomic(c: owlready2.entity.ThingClass):
        assert isinstance(c, owlready2.entity.ThingClass)
        if '¬' in c.name and not (' ' in c.name):
            return False
        elif ' ' in c.name or '∃' in c.name or '∀' in c.name:
            return False
        else:
            return True

    @staticmethod
    def __build_concepts_mapping(onto: Ontology) -> Tuple[Dict,
                                                          Concept,
                                                          Concept]:
        """
        Construct a mapping from full_iri to corresponding Concept objects.

        concept.namespace.base_iri + concept.name
        mappings from concepts uri to concept objects
            1) full_iri:= owlready2.ThingClass.namespace.base_iri +
                          owlready2.ThingClass.name
            2) Concept:
        """
        concepts = dict()
        individuals = set()
        T = Concept(owlready2.Thing,
                    kwargs={'form': 'Class'},
                    world=onto.world)
        bottom = Concept(owlready2.Nothing,
                         kwargs={'form': 'Class'},
                         world=onto.world)
        for i in onto.classes():
            temp_concept = Concept(i, kwargs={'form': 'Class'},
                                   world=onto.world)
            concepts[temp_concept.full_iri] = temp_concept
            individuals.update(temp_concept.instances)
        try:
            assert T.instances  # if empty throw error.
            assert individuals.issubset(T.instances)
        except AssertionError:
            print('Sanity checking failed: owlready2. \
                Thing does not contain any individual.\
                To allivate this issue, we explicitly \
                assign all individuals/instances to concept T.')
            T.instances = individuals

        concepts[T.full_iri] = T
        concepts[bottom.full_iri] = bottom
        return concepts, T, bottom

    def __build_hierarchy(self, onto: Ontology) -> None:
        """
        Builds concept sub and super classes hierarchies.

        1) self.top_down_concept_hierarchy is a mapping
           from Concept objects to a set of Concept objects that are
           direct subclasses of given Concept object.

        2) self.down_top_concept_hierarchy is a mapping
           from Concept objects to set of Concept objects that are
           direct superclasses of given Concept object.
        """

        self.concepts, self.thing, self.nothing = (
                        self.__build_concepts_mapping(onto))

        self.down_top_concept_hierarchy[self.thing] = set()
        # T should not subsume itself.
        self.top_down_concept_hierarchy[self.thing] = (
                {_ for _ in self.concepts.values() if _ is not self.thing})

        # second loop over concepts in the execution,
        for str_, concept_A in self.concepts.items():

            for desc in concept_A.owl.descendants(include_self=False,
                                                  world=onto.world):

                wrapped_desc = self.concepts[desc.namespace.base_iri +
                                             desc.name]

                # Include all sub class wrapped with AtomicConcept class.
                self.top_down_concept_hierarchy[concept_A].add(wrapped_desc)
                # if no descendant, then it is a leaf concept.
                if len(wrapped_desc.owl.descendants(
                        include_self=False, world=onto.world)) == 0:
                    self.concepts_to_leafs.setdefault(concept_A,
                                                      set()).add(wrapped_desc)

            for ans in concept_A.owl.ancestors(include_self=False):
                wrapped_ans = self.concepts[ans.namespace.base_iri + ans.name]
                # Include all superclasses into down top hierarchy
                self.down_top_concept_hierarchy[concept_A].add(wrapped_ans)
            # returns direct subclasses
            for subs in concept_A.owl.subclasses(world=onto.world):
                if concept_A.owl == subs:
                    continue
                subs_w = self.concepts[subs.namespace.base_iri + subs.name]

                self.top_down_direct_concept_hierarchy[concept_A].add(subs_w)
                self.down_top_direct_concept_hierarchy[subs_w].add(concept_A)

    def parse(self):
        """
        Top-down and bottom up hierarchies are constructed
        from owlready2.Ontology
        """
        self.__build_hierarchy(self.onto)
        self.property_hierarchy = PropertyHierarchy(self.onto)

    def get_leaf_concepts(self, concept: Concept):
        """ Return : { x | (x subClassOf concept) AND
                       not exist y: y subClassOf x )} """
        for leaf in self.concepts_to_leafs[concept]:
            yield leaf

    def negation(self, concept: Concept):
        """ Return a Concept object that is a negation of given concept."""
        return self.__concept_generator.negation(concept)

    def negation_from_iterables(self, s: Generator):
        """ Return : { x | ( x \\equv not s} """
        for item in s:
            yield self.__concept_generator.negation(item)

    def get_direct_sub_concepts(self, concept: Concept):
        """ Return : { x | ( x subClassOf concept )} """
        for v in self.top_down_direct_concept_hierarchy[concept]:
            yield v

    def get_all_sub_concepts(self, concept: Concept):
        """ Return : { x | ( x subClassOf concept ) OR ..."""
        for v in self.top_down_concept_hierarchy[concept]:
            yield v

    def get_direct_parents(self, concept: Concept):
        """ Return : { x | (concept subClassOf x)} """
        for direct_parent in self.down_top_direct_concept_hierarchy[concept]:
            yield direct_parent

    def most_general_existential_restrictions(self, concept: Concept):

        for prob in self.property_hierarchy.get_most_general_property():
            yield self.__concept_generator.existential_restriction(concept,
                                                                   prob)

    def most_general_universal_restriction(self, concept: Concept) -> Concept:
        assert isinstance(concept, Concept)
        for prob in self.property_hierarchy.get_most_general_property():
            yield self.__concept_generator.universal_restriction(concept, prob)

    def union(self, conceptA: Concept, conceptB: Concept) -> Concept:
        """Return a concept c == (conceptA OR conceptA)"""
        assert isinstance(conceptA, Concept)
        assert isinstance(conceptB, Concept)
        return self.__concept_generator.union(conceptA, conceptB)

    def intersection(self, conceptA: Concept, conceptB: Concept) -> Concept:
        """Return a concept c == (conceptA AND conceptA)"""
        assert isinstance(conceptA, Concept)
        assert isinstance(conceptB, Concept)
        return self.__concept_generator.intersection(conceptA, conceptB)

    def existential_restriction(self, concept: Concept, property_) -> Concept:
        """Return a concept c == (Exist R.C)"""
        assert isinstance(concept, Concept)
        return self.__concept_generator.existential_restriction(concept,
                                                                property_)

    def universal_restriction(self, concept: Concept, property_) -> Concept:
        """Return a concept c == (Forall R.C)"""
        assert isinstance(concept, Concept)
        return self.__concept_generator.universal_restriction(concept,
                                                              property_)

    def get_all_concepts(self):
        return self.concepts.values()


class PropertyHierarchy:

    def __init__(self, onto):
        self.all_properties = [i for i in onto.properties()]

        self.data_properties = [i for i in onto.data_properties()]

        self.object_properties = [i for i in onto.object_properties()]

        self.annotation_properties = [i for i in onto.annotation_properties()]

    def get_most_general_property(self):
        for i in self.all_properties:
            yield i
