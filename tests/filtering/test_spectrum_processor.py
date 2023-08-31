import ast
import os
import numpy as np
import pytest
from matchms import SpectrumProcessor
from matchms.SpectrumProcessor import ALL_FILTERS, ProcessingReport
from ..builder_Spectrum import SpectrumBuilder


@pytest.fixture
def spectrums():
    metadata1 = {"charge": "+1",
                 "pepmass": 100}
    metadata2 = {"charge": "-1",
                 "pepmass": 102}
    metadata3 = {"charge": -1,
                 "pepmass": 104}

    s1 = SpectrumBuilder().with_metadata(metadata1).build()
    s2 = SpectrumBuilder().with_metadata(metadata2).build()
    s3 = SpectrumBuilder().with_metadata(metadata3).build()
    return [s1, s2, s3]


def test_filter_sorting_and_output():
    processing = SpectrumProcessor("default")
    expected_filters = ['make_charge_int',
                        'add_compound_name',
                        ('derive_adduct_from_name', {'remove_adduct_from_name': True}),
                        ('derive_formula_from_name', {'remove_formula_from_name': True}),
                        'clean_compound_name',
                        'interpret_pepmass',
                        'add_precursor_mz',
                        'derive_ionmode',
                        'correct_charge',
                        ('require_precursor_mz', {'minimum_accepted_mz': 10.0}),
                        ('add_parent_mass',
                         {'estimate_from_adduct': True, 'overwrite_existing_entry': False}),
                        ('harmonize_undefined_inchikey', {'aliases': None, 'undefined': ''}),
                        ('harmonize_undefined_inchi', {'aliases': None, 'undefined': ''}),
                        ('harmonize_undefined_smiles', {'aliases': None, 'undefined': ''}),
                        'repair_inchi_inchikey_smiles',
                        'normalize_intensities']
    assert processing.processing_steps == expected_filters


@pytest.mark.parametrize("filter_step, expected", [
    [("add_parent_mass", {'estimate_from_adduct': False}),
     ('add_parent_mass', {'estimate_from_adduct': False, 'overwrite_existing_entry': False})],
    ["derive_adduct_from_name",
     ('derive_adduct_from_name', {'remove_adduct_from_name': True})],
    [("require_correct_ionmode", {"ion_mode_to_keep": "both"}),
     ("require_correct_ionmode", {"ion_mode_to_keep": "both"})],
])
def test_overwrite_default_settings(filter_step, expected):
    """Test if both default settings and set settings are returned in processing steps"""
    processor = SpectrumProcessor(None)
    processor.add_filter(filter_step)
    expected_filters = [expected]
    assert processor.processing_steps == expected_filters


def test_incomplete_parameters():
    """Test if an error is raised when running an incomplete command"""
    with pytest.raises(AssertionError):
        processor = SpectrumProcessor(None)
        processor.add_filter("require_correct_ionmode")


def test_string_output():
    processing = SpectrumProcessor("minimal")
    expected_str = "SpectrumProcessor\nProcessing steps:\n- make_charge_int\n- interpret_pepmass" \
                   "\n- derive_ionmode\n- correct_charge"
    assert str(processing) == expected_str


@pytest.mark.parametrize("metadata, expected", [
    [{}, None],
    [{"ionmode": "positive"}, {"ionmode": "positive", "charge": 1}],
    [{"ionmode": "positive", "charge": 2}, {"ionmode": "positive", "charge": 2}],
])
def test_add_matchms_filter(metadata, expected):
    spectrum_in = SpectrumBuilder().with_metadata(metadata).build()
    processor = SpectrumProcessor("minimal")
    processor.add_matchms_filter(("require_correct_ionmode",
                                  {"ion_mode_to_keep": "both"}))
    spectrum = processor.process_spectrum(spectrum_in)
    if expected is None:
        assert spectrum is None
    else:
        assert dict(spectrum.metadata) == expected


def test_no_filters():
    spectrum_in = SpectrumBuilder().with_metadata({}).build()
    processor = SpectrumProcessor(predefined_pipeline=None)
    with pytest.raises(TypeError) as msg:
        _ = processor.process_spectrum(spectrum_in)
    assert str(msg.value) == "No filters to process"


def test_unknown_keyword():
    with pytest.raises(ValueError) as msg:
        _ = SpectrumProcessor(predefined_pipeline="something_wrong")
    assert "Unknown processing pipeline" in str(msg.value)


def test_filter_spectrums(spectrums):
    processor = SpectrumProcessor("minimal")
    spectrums = processor.process_spectrums(spectrums)
    assert len(spectrums) == 3
    actual_masses = [s.get("precursor_mz") for s in spectrums]
    expected_masses = [100, 102, 104]
    assert actual_masses == expected_masses


def test_filter_spectrums_report(spectrums):
    processor = SpectrumProcessor("minimal")
    spectrums, report = processor.process_spectrums(spectrums, create_report=True)
    assert len(spectrums) == 3
    actual_masses = [s.get("precursor_mz") for s in spectrums]
    expected_masses = [100, 102, 104]
    assert actual_masses == expected_masses
    assert report.counter_number_processed == 3
    assert report.counter_changed_field == {'make_charge_int': 2}
    assert report.counter_added_field == {'interpret_pepmass': 3, 'derive_ionmode': 3}
    report_df = report.to_dataframe()
    assert np.all(report_df.loc[["make_charge_int", "interpret_pepmass", "derive_ionmode"]].values == np.array(
        [[0, 2, 0],
         [0, 0, 3],
         [0, 0, 3]]))


def test_processing_report_class(spectrums):
    processing_report = ProcessingReport()
    for s in spectrums:
        spectrum_processed = s.clone()
        spectrum_processed.set("smiles", "test")
        processing_report.add_to_report(s, spectrum_processed, "test_filter")

    assert not processing_report.counter_removed_spectrums
    assert not processing_report.counter_changed_field
    assert processing_report.counter_added_field == {"test_filter": 3}


def test_adding_custom_filter(spectrums):
    def nonsense_inchikey(s):
        s_in = s.clone()
        s_in.set("inchikey", "NONSENSE")
        return s_in

    processor = SpectrumProcessor("minimal")
    processor.add_custom_filter(nonsense_inchikey)
    filters = processor.filters
    assert filters[-1].__name__ == "nonsense_inchikey"
    spectrums, report = processor.process_spectrums(spectrums, create_report=True)
    assert report.counter_number_processed == 3
    assert report.counter_changed_field == {'make_charge_int': 2}
    assert report.counter_added_field == {'interpret_pepmass': 3, 'derive_ionmode': 3, 'nonsense_inchikey': 3}
    assert spectrums[0].get("inchikey") == "NONSENSE", "Custom filter not executed properly"


def test_adding_custom_filter_with_parameters(spectrums):
    def nonsense_inchikey_multiple(s, number):
        s_in = s.clone()
        s_in.set("inchikey", number * "NONSENSE")
        return s_in

    processor = SpectrumProcessor("minimal")
    processor.add_custom_filter(nonsense_inchikey_multiple, {"number": 2})
    filters = processor.filters
    assert filters[-1].__name__ == "nonsense_inchikey_multiple"
    spectrums, report = processor.process_spectrums(spectrums, create_report=True)
    assert report.counter_number_processed == 3
    assert report.counter_changed_field == {'make_charge_int': 2}
    assert report.counter_added_field == {'interpret_pepmass': 3, 'derive_ionmode': 3, 'nonsense_inchikey_multiple': 3}
    assert spectrums[0].get("inchikey") == "NONSENSENONSENSE", "Custom filter not executed properly"


def test_add_filter_with_custom(spectrums):
    def nonsense_inchikey_multiple(s, number):
        s.set("inchikey", number * "NONSENSE")
        return s

    processor = SpectrumProcessor("minimal")
    processor.add_filter((nonsense_inchikey_multiple, {"number": 2}))
    filters = processor.filters
    assert filters[-1].__name__ == "nonsense_inchikey_multiple"
    spectrums, _ = processor.process_spectrums(spectrums, create_report=True)
    assert spectrums[0].get("inchikey") == "NONSENSENONSENSE", "Custom filter not executed properly"


def test_add_filter_with_matchms_filter(spectrums):
    processor = SpectrumProcessor("minimal")
    processor.add_filter(("require_correct_ionmode",
                          {"ion_mode_to_keep": "both"}))
    filters = processor.filters
    assert filters[-1].__name__ == "require_correct_ionmode"
    spectrums, _ = processor.process_spectrums(spectrums, create_report=True)
    assert not spectrums, "Expected to be empty list"


def test_all_filters_is_complete():
    """Checks that the global varible ALL_FILTERS contains all the available filters

    This is important, since performing tests in the wrong order can make some filters useless.
    """

    def get_functions_from_file(file_path):
        """Gets all python functions in a file"""
        with open(file_path, 'r', encoding="utf-8") as file:
            tree = ast.parse(file.read(), filename=file_path)
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append(node.name)
        return functions

    current_dir = os.path.dirname(os.path.abspath(__file__))
    filtering_directory = os.path.join(current_dir, "../../matchms/filtering")
    directories_with_filters = ["metadata_processing",
                                "peak_processing"]

    all_filters = [filter.__name__ for filter in ALL_FILTERS]
    list_of_filter_function_names = []
    for directory_with_filters in directories_with_filters:
        directory_with_filters = os.path.join(filtering_directory, directory_with_filters)
        scripts = os.listdir(directory_with_filters)
        for script in scripts:
            # Remove __init__
            if script[0] == "_":
                break
            if script[-3:] == ".py":
                functions = get_functions_from_file(os.path.join(directory_with_filters, script))
                for function in functions:
                    if function[0] != "_":
                        list_of_filter_function_names.append((script, function))
    for script, filter_function in list_of_filter_function_names:
        assert filter_function in all_filters, \
            f"The function {filter_function} in the script {script} is not given in ALL_FILTERS, " \
            f"this should be added to ensure a correct order of filter functions." \
            f"If this function is not a filter add a _ before the function name"


def test_all_filters_no_duplicates():
    all_filters = [filter.__name__ for filter in ALL_FILTERS]
    assert len(all_filters) == len(set(all_filters)), "One of the filters appears twice in ALL_FILTERS"
