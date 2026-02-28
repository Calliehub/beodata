from logging_config import get_logger
from sources.abbreviations import Abbreviations
from sources.analytical_lexicon import AnalyticalLexicon
from sources.bosworth import BosworthToller
from sources.brunanburh import Brunanburh
from sources.brunanburh_normalized import BrunanburhNormalized
from sources.brunetti import Brunetti
from sources.ebeowulf import EBeowulf
from sources.heorot import Heorot
from sources.mcmaster import McMaster
from sources.mit import Mit
from sources.oldenglishaerobics import OldEnglishAerobics
from sources.perseus import Perseus

# (class, attribute name)
SOURCES = [
    (BosworthToller, "bt"),
    (Abbreviations, "abbv"),
    (Brunetti, "brunetti"),
    (Mit, "mit"),
    (McMaster, "mcmaster"),
    (EBeowulf, "ebeowulf"),
    (Perseus, "perseus"),
    (OldEnglishAerobics, "oea"),
    (AnalyticalLexicon, "lexicon"),
    (Heorot, "heorot"),
    (Brunanburh, "brunanburh"),
    (BrunanburhNormalized, "brunanburh_normalized"),
]


class Beodata:
    def __repr__(self) -> str:
        attrs = [
            f"  .{name} ({type(getattr(self, name)).__name__})"
            for _, name in SOURCES
            if hasattr(self, name)
        ]
        return "beodata namespace:\n" + "\n".join(attrs)


def repl() -> Beodata:
    ns = Beodata()
    ns.logger = get_logger()
    for cls, name in SOURCES:
        obj = cls()
        obj.load()
        setattr(ns, name, obj)
    print("Beodata loaded! To run repl: ")
    print("  poetry run python -i repl")
    print()
    print(f"Inside that repl you will have the {str(ns)}")
    print()
    print("Or, run the MCP server: ")
    print("  poetry run server")

    return ns


if __name__ == "__main__":
    beodata = repl()
