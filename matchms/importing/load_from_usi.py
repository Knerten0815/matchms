import json
import numpy as np
import requests
from ..logging import logger
from ..Spectrum import Spectrum


def load_from_usi(usi: str, server: str = "https://metabolomics-usi.ucsd.edu"):
    """Load spectrum from metabolomics USI.

    USI returns JSON data with keys "peaks", "n_peaks" and "precuror_mz"

    .. code-block:: python

        from matchms.importing import load_from_usi

        spectrum = load_from_usi("mzspec:MASSBANK::accession:SM858102")
        print(f"Found spectrum with precursor m/z of {spectrum.get("precursor_mz"):.2f}.")

    Parameters
    ----------
    usi:
        Provide the usi.

    server: string
        USI server
    """

    # Create the url
    url = server + "/json/?usi=" + usi
    metadata = {"usi": usi, "server": server}
    response = requests.get(url)

    if response.status_code == 404:
        return None
    # Extract data and create Spectrum object
    try:
        spectral_data = response.json()
        if spectral_data is None or "peaks" not in spectral_data:
            logger.info("Empty spectrum found (no data found). Will not be imported.")
            return None
        peaks = spectral_data["peaks"]
        if len(peaks) == 0:
            logger.info("Empty spectrum found (no peaks in 'peaks_json'). Will not be imported.")
            return None
        mz_list, intensity_list = zip(*peaks)
        mz_array = np.array(mz_list)
        intensity_array = np.array(intensity_list)

        metadata["precursor_mz"] = spectral_data.get("precursor_mz", None)

        s = Spectrum(mz_array, intensity_array, metadata)

        return s

    except json.decoder.JSONDecodeError:
        logger.warning("Failed to unpack json (JSONDecodeError).")
        return None
