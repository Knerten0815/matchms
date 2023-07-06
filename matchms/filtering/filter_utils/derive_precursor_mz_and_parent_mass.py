import logging
from matchms.constants import PROTON_MASS
from matchms.filtering.filter_utils.interpret_unknown_adduct import \
    get_multiplier_and_mass_from_adduct
from matchms.filtering.metadata_processing.clean_adduct import (
    _clean_adduct, load_known_adducts)


logger = logging.getLogger("matchms")


def derive_parent_mass_from_precursor_mz(spectrum, estimate_from_adduct):
    if spectrum is None:
        return None

    precursor_mz = spectrum.get("precursor_mz", None)
    if precursor_mz is None:
        logger.warning("Missing precursor m/z to derive parent mass.")
        return None
    charge = _get_charge(spectrum)

    if estimate_from_adduct:
        multiplier, correction_mass = _get_multiplier_and_correction_mass_from_adduct(
            spectrum.get("adduct"))
        if correction_mass is not None and multiplier is not None:
            parent_mass = (precursor_mz - correction_mass) / multiplier
            return parent_mass

    if _is_valid_charge(charge):
        # Assume adduct of shape [M+xH] or [M-xH]
        protons_mass = PROTON_MASS * charge
        precursor_mass = precursor_mz * abs(charge)
        parent_mass = precursor_mass - protons_mass
        return parent_mass
    return None


def derive_precursor_mz_from_parent_mass(spectrum):
    """Derives the precursor_mz from the parent mass and adduct or charge"""
    estimate_from_adduct = True
    if spectrum is None:
        return None

    parent_mass = spectrum.get("parent_mass")
    if parent_mass is None:
        logger.warning("Missing parent mass to derive precursor mz.")
        return None
    if estimate_from_adduct:
        multiplier, correction_mass = _get_multiplier_and_correction_mass_from_adduct(
            spectrum.get("adduct"))
        if correction_mass is not None and multiplier is not None:
            precursor_mz = parent_mass * multiplier + correction_mass
            return precursor_mz

    charge = _get_charge(spectrum)
    if _is_valid_charge(charge):
        # Assume adduct of shape [M+xH] or [M-xH]
        protons_mass = PROTON_MASS * charge
        precursor_mass = parent_mass + protons_mass
        precursor_mz = precursor_mass / abs(charge)
        return precursor_mz
    logger.error("Precursor mz could not be derived from parent mass, since charge and adduct were missing")
    return None


def _get_multiplier_and_correction_mass_from_adduct(adduct):
    adduct = _clean_adduct(adduct)
    known_adducts = load_known_adducts()

    if adduct in list(known_adducts["adduct"]):
        multiplier = known_adducts.loc[known_adducts["adduct"] == adduct, "mass_multiplier"].values[0]
        correction_mass = known_adducts.loc[known_adducts["adduct"] == adduct, "correction_mass"].values[0]
    else:
        multiplier, correction_mass = get_multiplier_and_mass_from_adduct("adduct")
    return multiplier, correction_mass


def _is_valid_charge(charge):
    return (charge is not None) and (charge != 0)


def _get_charge(spectrum):
    """Get charge from `Spectrum()` object.
    In case no valid charge is found, guess +1 or -1 based on ionmode.
    Else return 0.
    """
    charge = spectrum.get("charge")
    if _is_valid_charge(charge):
        return charge
    if spectrum.get('ionmode') == "positive":
        logger.info(
            "Missing charge entry, but positive ionmode detected. "
            "Consider prior run of `correct_charge()` filter.")
        return 1
    if spectrum.get('ionmode') == "negative":
        logger.info(
            "Missing charge entry, but negative ionmode detected. "
            "Consider prior run of `correct_charge()` filter.")
        return -1

    logger.warning(
        "Missing charge and ionmode entries. "
        "Consider prior run of `derive_ionmode()` and `correct_charge()` filters.")
    return 0
