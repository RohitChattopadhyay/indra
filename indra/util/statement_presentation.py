from collections import defaultdict
from itertools import permutations

from indra.assemblers.english import EnglishAssembler
from indra.statements import Agent, get_statement_by_name


def _get_keyed_stmts(stmt_list):
    def name(agent):
        return 'None' if agent is None else agent.name

    for s in stmt_list:
        # Create a key.
        verb = s.__class__.__name__
        key = (verb,)
        ags = s.agent_list()
        if verb == 'Complex':
            ag_ns = {name(ag) for ag in ags}
            if 1 < len(ag_ns) < 6:
                for pair in permutations(ag_ns, 2):
                    yield key + tuple(pair),  s
            if len(ag_ns) == 2:
                continue
            key += tuple(sorted(ag_ns))
        elif verb == 'Conversion':
            subj = name(s.subj)
            objs_from = {name(ag) for ag in s.obj_from}
            objs_to = {name(ag) for ag in s.obj_to}
            key += (subj, tuple(sorted(objs_from)), tuple(sorted(objs_to)))
        elif verb == 'ActiveForm':
            key += (name(ags[0]), s.activity, s.is_active)
        elif verb == 'HasActivity':
            key += (name(ags[0]), s.activity, s.has_activity)
        else:
            key += tuple([name(ag) for ag in ags])

        yield key, s


def group_and_sort_statements(stmt_list, ev_totals=None):
    """Group statements by type and arguments, and sort by prevalence.

    Parameters
    ----------
    stmt_list : list[Statement]
        A list of INDRA statements.
    ev_totals : dict{int: int}
        A dictionary, keyed by statement hash (shallow) with counts of total
        evidence as the values. Including this will allow statements to be
        better sorted.

    Returns
    -------
    sorted_groups : list[tuple]
        A list of tuples containing a sort key, the statement type, and a list
        of statements, also sorted by evidence count, for that key and type.
        The sort key contains a count of statements with those argument, the
        arguments (normalized strings), the count of statements with those
        arguements and type, and then the statement type.
    """
    def _count(stmt):
        sh = stmt.get_hash()
        if ev_totals is None or sh not in ev_totals:
            return len(stmt.evidence)
        else:
            return ev_totals[sh]

    stmt_rows = defaultdict(list)
    stmt_counts = defaultdict(lambda: 0)
    arg_counts = defaultdict(lambda: 0)
    for key, s in _get_keyed_stmts(stmt_list):
        # Update the counts, and add key if needed.
        stmt_rows[key].append(s)

        # Keep track of the total evidence counts for this statement and the
        # arguments.
        stmt_counts[key] += _count(s)

        # Add up the counts for the arguments, pairwise for Complexes and
        # Conversions. This allows, for example, a complex between MEK, ERK,
        # and something else to lend weight to the interactions between MEK
        # and ERK.
        if key[0] == 'Conversion':
            subj = key[1]
            for obj in key[2] + key[3]:
                arg_counts[(subj, obj)] += _count(s)
        else:
            arg_counts[key[1:]] += _count(s)

    # Sort the rows by count and agent names.
    def process_rows(stmt_rows):
        for key, stmts in stmt_rows.items():
            verb = key[0]
            inps = key[1:]
            sub_count = stmt_counts[key]
            arg_count = arg_counts[inps]
            if verb == 'Complex' and sub_count == arg_count and len(inps) <= 2:
                if all([len(set(ag.name for ag in s.agent_list())) > 2
                        for s in stmts]):
                    continue
            new_key = (arg_count, inps, sub_count, verb)
            stmts = sorted(stmts,
                           key=lambda s: _count(s) + 1/(1+len(s.agent_list())),
                           reverse=True)
            yield new_key, verb, stmts

    sorted_groups = sorted(process_rows(stmt_rows),
                           key=lambda tpl: tpl[0], reverse=True)

    return sorted_groups


def make_stmt_from_sort_key(key, verb):
    """Make a Statement from the sort key.

    Specifically, the sort key used by `group_and_sort_statements`.
    """
    def make_agent(name):
        if name == 'None' or name is None:
            return None
        return Agent(name)

    StmtClass = get_statement_by_name(verb)
    inps = list(key[1])
    if verb == 'Complex':
        stmt = StmtClass([make_agent(name) for name in inps])
    elif verb == 'Conversion':
        stmt = StmtClass(make_agent(inps[0]),
                         [make_agent(name) for name in inps[1]],
                         [make_agent(name) for name in inps[2]])
    elif verb == 'ActiveForm' or verb == 'HasActivity':
        stmt = StmtClass(make_agent(inps[0]), inps[1], inps[2])
    else:
        stmt = StmtClass(*[make_agent(name) for name in inps])
    return stmt


def stmt_to_english(stmt):
    """Return an English assembled Statement as a sentence."""
    ea = EnglishAssembler([stmt])
    return ea.make_model()[:-1]


def make_string_from_sort_key(key, verb):
    """Make a Statement string via EnglishAssembler from the sort key.

    Specifically, the sort key used by `group_and_sort_statements`.
    """
    stmt = make_stmt_from_sort_key(key, verb)
    return stmt_to_english(stmt)


def get_simplified_stmts(stmts):
    simple_stmts = []
    for key, s in _get_keyed_stmts(stmts):
        simple_stmts.append(make_stmt_from_sort_key(key, s.__class__.__name__))
    return simple_stmts
