/**
 * Set up all the counters on the page.
 */
function setupCounters() {
    const data = BC19.countersData;

    BC19.setCounter('total-cases-counter', data.totalCases);
    BC19.setCounter('deaths-counter', data.totalDeaths);
    BC19.setCounter('in-isolation-counter', data.inIsolation);
    BC19.setCounter('hospitalized-counter', data.allHospitalized);
    BC19.setCounter('icu-counter', data.inICU);
    BC19.setCounter('school-year-student-cases',
                    data.schoolYearNewStudentCasesTotal);
    BC19.setCounter('school-year-staff-cases',
                    data.schoolYearNewStaffCasesTotal);
    BC19.setCounter('vaccines-1dose-pct-counter', data.vaccines1DosePct);
    BC19.setCounter('vaccines-full-doses-pct-counter',
                    data.vaccinesFullDosesPct);
    BC19.setCounter('total-tests-counter', data.totalTests);
    BC19.setCounter('positive-test-results-counter', data.positiveTestResults);
    BC19.setCounter('positive-test-rate-counter', data.positiveTestRate);
    BC19.setCounter('jail-inmate-pop-counter', data.jailInmatePop);
    BC19.setCounter('jail-inmate-total-tests', data.jailInmateTotalTests);
    BC19.setCounter('jail-inmate-cur-cases', data.jailInmateCurCases);
    BC19.setCounter('jail-inmate-pos-rate', data.jailInmatePosRate);
    BC19.setCounter('jail-staff-total-tests', data.jailStaffTotalTests);
    BC19.setCounter('jail-staff-total-cases', data.jailStaffTotalCases);
};


/**
 * Set up the bar graphs.
 */
function setupBarGraphs() {
    const data = BC19.barGraphsData;

    BC19.setupBarGraph(
        d3.select('#by_age_graph'),
        {
            pct: true,
        },
        data.casesByAge);

    BC19.setupBarGraph(
        d3.select('#by_region_graph'),
        {
            pct: true,
        },
        data.casesByRegion);

    BC19.setupBarGraph(
        d3.select('#deaths_by_age_graph'),
        {
            skipIfZero: true,
        },
        data.deathsByAge);

    BC19.setupBarGraph(
        d3.select('#mortality_by_age_graph'),
        {
            skipIfZero: true,
            formatValue: (value) => {
                const normValue = value.toLocaleString(undefined, {
                    maximumFractionDigits: 2,
                });

                return normValue !== '0' ? `${normValue}%` : '';
            }
        },
        data.mortalityRate);

    BC19.setupBarGraph(
        d3.select('#by_hospital_graph'),
        {},
        data.byHospital);
};


/**
 * Set up the main timeline graphs.
 *
 * This will set up:
 *
 *     * Total Confirmed Cases
 *     * New Cases
 *     * 14-Day New Case Rate
 *     * Total Deaths
 *     * New Deaths
 *     * Cases By Age
 *     * Cases By Region
 *     * 7-Day Test Positivity Rate
 *     * % of Cases In Each Batch of Test Results
 *     * Test Results
 *     * Total Hospitalizations vs. ICU
 *     * Hospitalized Butte County Residents
 *     * People In Isolation
 *     * Skilled Nursing Facility Cases
 *     * Skilled Nursing Facility Deaths
 *     * Current Inmate Cases
 *     * Total Staff Cases
 */
function setupTimelineGraphs() {
    const graphData = BC19.graphData;
    const maxValues = BC19.maxValues;
    const tickCounts = BC19.tickCounts;
    const isolationData = graphData.isolation;
    const casesI = BC19.latestRowIndexes.cases;

    const axisX = {
        type: 'timeseries',
        localtime: false,
        label: {
            position: 'outer-left',
        },
        tick: {
            culling: true,
            fit: false,
            format: '%b %d',
            multiline: true,
        },
        min: BC19.defaultTimelineDomain[0],
        max: BC19.defaultTimelineDomain[1],
    };

    BC19.setupBBGraph({
        bindto: '#total_cases_graph',
        size: {
            height: BC19.graphSizes.VERY_TALL,
        },
        data: {
            x: 'date',
            colors: BC19.colors,
            columns: [
                graphData.dates,
                graphData.cases.totalCases,
            ],
            names: {
                cases: 'Total Cases',
            },
            types: {
                cases: 'area-step',
            },
        },
        grid: {
            x: {
                lines: graphData.notes,
            },
            y: {
                show: true,
            },
        },
        axis: {
            x: axisX,
            y: {
                max: BC19.getMaxY(maxValues.totalCases, tickCounts.VERY_TALL),
                padding: 0,
                tick: {
                    stepSize: BC19.getStepSize(
                        maxValues.totalCases,
                        tickCounts.VERY_TALL),
                },
            },
        },
    });

    BC19.setupBBGraph({
        bindto: '#new_cases_graph',
        size: {
            height: BC19.graphSizes.STANDARD,
        },
        data: {
            x: 'date',
            colors: BC19.colors,
            columns: [graphData.dates, graphData.cases.newCases],
            names: {
                new_cases: 'New Cases',
            },
            types: {
                new_cases: 'bar',
            },
        },
        axis: {
            x: axisX,
            y: {
                max: BC19.getMaxY(maxValues.newCases, tickCounts.STANDARD),
                padding: 0,
                tick: {
                    stepSize: BC19.getStepSize(maxValues.newCases,
                                               tickCounts.STANDARD),
                },
            },
        },
    });

    const per1KPop = BC19.COUNTY_POPULATION / 1000;
    const per1KPopRound = Math.round(per1KPop);

    BC19.setupBBGraph({
        bindto: '#one_week_new_case_rate_graph',
        size: {
            height: BC19.graphSizes.STANDARD,
        },
        data: {
            x: 'date',
            colors: BC19.colors,
            columns: [
                graphData.dates,
                graphData.cases.oneWeekNewCaseRate,
            ],
            names: {
                new_case_rate: 'New Cases Past 7 Days',
            },
            types: {
                new_case_rate: 'area',
            },
        },
        axis: {
            x: axisX,
            y: {
                max: BC19.getMaxY(Math.max(90, maxValues.oneWeekCaseRate),
                                  tickCounts.STANDARD),
                padding: 0,
                tick: {
                    stepSize: BC19.getStepSize(maxValues.oneWeekCaseRate,
                                               tickCounts.STANDARD),
                },
            },
        },
        grid: {
            y: {
                lines: [
                    {
                        value: 70,
                        text: 'Extreme',
                        position: 'start',
                        class: '-is-severity-extreme',
                    },
                    {
                        value: 25,
                        text: 'Critical',
                        position: 'start',
                        class: '-is-severity-critical',
                    },
                    {
                        value: 10,
                        text: 'High',
                        position: 'start',
                        class: '-is-severity-high',
                    },
                    {
                        value: 1,
                        text: 'Medium',
                        position: 'start',
                        class: '-is-severity-medium',
                    },
                ],
            },
        },
        tooltip: {
            linked: true,

            format: {
                value: (value, ratio, id) => {
                    const normValue = value.toFixed(1);
                    const cases = Math.round(
                        value * 7 * (BC19.COUNTY_POPULATION / 100000));
                    return `${normValue} per 100K people per day (~${cases})`;
                },
            },
        },
    });

    BC19.setupBBGraph({
        bindto: '#total_deaths_graph',
        size: {
            height: BC19.graphSizes.SMALL,
        },
        data: {
            x: 'date',
            colors: BC19.colors,
            columns: [
                BC19.graphData.dates,
                BC19.graphData.deaths.totalDeaths,
            ],
            names: {
                total_deaths: 'Total Deaths',
            },
            types: {
                total_deaths: 'area-step',
            },
        },
        axis: {
            x: axisX,
            y: {
                max: BC19.getMaxY(maxValues.totalDeaths,
                                  tickCounts.SMALL),
                padding: 0,
                tick: {
                    stepSize: BC19.getStepSize(maxValues.totalDeaths,
                                               tickCounts.SMALL),
                },
            },
        },
    });

    BC19.setupBBGraph({
        bindto: '#new_deaths_graph',
        size: {
            height: BC19.graphSizes.SMALL,
        },
        data: {
            x: 'date',
            colors: BC19.colors,
            columns: [graphData.dates, graphData.deaths.newDeaths],
            names: {
                new_deaths: 'New Deaths',
            },
            types: {
                new_deaths: 'bar',
            },
        },
        axis: {
            x: axisX,
            y: {
                max: BC19.getMaxY(maxValues.newDeaths, tickCounts.SMALL),
                padding: 0,
                tick: {
                    stepSize: BC19.getStepSize(maxValues.newDeaths,
                                               tickCounts.SMALL),
                },
            },
        },
    });

    BC19.setupBBGraph({
        bindto: '#schools_semester_cases',
        size: {
            height: BC19.graphSizes.MEDIUM,
        },
        data: {
            x: 'date',
            colors: BC19.colors,
            columns: [
                graphData.dates,
                graphData.schools.semesterStudentCasesRemote,
                graphData.schools.semesterStudentCasesLocal,
                graphData.schools.semesterStaffCasesRemote,
                graphData.schools.semesterStaffCasesLocal,
            ],
            names: {
                semester_staff_local: 'Staff (in person)',
                semester_staff_remote: 'Staff (remote)',
                semester_students_local: 'Students (in person)',
                semester_students_remote: 'Students (remote)',
            },
            order: null,
            groups: [
                [
                    'semester_students_local',
                    'semester_students_remote',
                    'semester_staff_local',
                    'semester_staff_remote',
                ],
            ],
            type: 'area-step',
        },
        axis: {
            x: axisX,
            y: {
                max: BC19.getMaxY(maxValues.semesterSchoolCases,
                                  tickCounts.MEDIUM),
                padding: 0,
                tick: {
                    stepSize: BC19.getStepSize(maxValues.semesterSchoolCases,
                                               tickCounts.MEDIUM),
                },
            },
        },
        legend: {
            show: true,
        },
    });

    BC19.setupBBGraph({
        bindto: '#schools_new_cases',
        size: {
            height: BC19.graphSizes.MEDIUM,
        },
        data: {
            x: 'date',
            colors: BC19.colors,
            columns: [
                graphData.dates,
                graphData.schools.newStudentCasesRemote,
                graphData.schools.newStudentCasesLocal,
                graphData.schools.newStaffCasesRemote,
                graphData.schools.newStaffCasesLocal,
            ],
            names: {
                new_staff_local: 'Staff (in person)',
                new_staff_remote: 'Staff (remote)',
                new_students_local: 'Students (in person)',
                new_students_remote: 'Students (remote)',
            },
            order: null,
            groups: [
                [
                    'new_students_local',
                    'new_students_remote',
                    'new_staff_local',
                    'new_staff_remote',
                ],
            ],
            type: 'bar',
        },
        axis: {
            x: axisX,
            y: {
                max: BC19.getMaxY(maxValues.newSchoolCases,
                                  tickCounts.MEDIUM),
                padding: 0,
                tick: {
                    stepSize: BC19.getStepSize(maxValues.newSchoolCases,
                                               tickCounts.MEDIUM),
                },
            },
        },
        legend: {
            show: true,
        },
    });

    BC19.setupBBGraph({
        bindto: '#cases_by_age_timeline_graph',
        size: {
            height: BC19.graphSizes.VERY_TALL,
        },
        data: {
            x: 'date',
            colors: BC19.colors,
            columns: [
                graphData.dates,
            ].concat(graphData.ageRanges),
            names: {
                age_0_4: '0-4',
                age_5_12: '5-12',
                age_13_17: '13-17',
                age_18_24: '18-24',
                age_25_34: '25-34',
                age_35_44: '35-44',
                age_45_54: '45-54',
                age_55_64: '55-64',
                age_65_74: '65-74',
                age_75_plus: '75+',

                age_0_17: '0-17 (Historical)',
                age_18_49: '18-49 (Historical)',
                age_50_64: '50-64 (Historical)',
                age_65_plus: '65+ (Historical)',
            },
            order: null,
            type: 'area-step',
            groups: [
                [
                    'age_0_4',
                    'age_5_12',
                    'age_13_17',
                    'age_18_24',
                    'age_25_34',
                    'age_35_44',
                    'age_45_54',
                    'age_55_64',
                    'age_65_74',
                    'age_75_plus',

                    'age_0_17',
                    'age_18_49',
                    'age_50_64',
                    'age_65_plus',
                ],
            ],
        },
        axis: {
            x: axisX,
            y: {
                max: BC19.getMaxY(maxValues.totalCases, tickCounts.VERY_TALL),
                padding: 0,
                tick: {
                    stepSize: BC19.getStepSize(maxValues.totalCases,
                                               tickCounts.VERY_TALL),
                },
            },
        },
        legend: {
            show: true,
        },
    });

    BC19.setupBBGraph({
        bindto: '#cases_by_region_timeline_graph',
        size: {
            height: BC19.graphSizes.VERY_TALL,
        },
        data: {
            x: 'date',
            colors: BC19.colors,
            columns: [
                graphData.dates,
                graphData.regions.chico,
                graphData.regions.oroville,
                graphData.regions.gridley,
                graphData.regions.biggsGridley,
                graphData.regions.durham,
                graphData.regions.ridge,
                graphData.regions.other,
            ],
            names: {
                biggs_gridley: 'Biggs/Gridley',
                chico: 'Chico',
                durham: 'Durham',
                gridley: 'Gridley (Historical)',
                oroville: 'Oroville',
                other: 'Other',
                ridge: 'Paradise/Magalia/Ridge Communities',
            },
            order: null,
            type: 'area-step',
            groups: [
                [
                    'oroville', 'gridley', 'biggs_gridley', 'other', 'chico',
                    'durham', 'ridge',
                ],
            ],
        },
        axis: {
            x: axisX,
            y: {
                max: BC19.getMaxY(maxValues.totalCases, tickCounts.VERY_TALL),
                padding: 0,
                tick: {
                    stepSize: BC19.getStepSize(maxValues.totalCases,
                                               tickCounts.VERY_TALL),
                },
            },
        },
        legend: {
            show: true,
        },
    });

    BC19.setupBBGraph({
        bindto: '#cases_in_test_results_graph',
        size: {
            height: BC19.graphSizes.STANDARD,
        },
        data: {
            x: 'date',
            colors: BC19.colors,
            columns: [
                graphData.dates,
                graphData.viralTests.negativeResults,
                graphData.viralTests.positiveResults,
            ],
            groups: [['neg_results', 'pos_results']],
            names: {
                neg_results: 'Negative Test Results',
                pos_results: 'Positive Test Results',
            },
            stack: {
                normalize: true,
            },
            type: 'bar',
        },
        axis: {
            x: axisX,
            y: {
                tick: {
                    stepSize: 25,
                },
            },
        },
        bar: {
            width: {
                ratio: 1.5,
            },
        },
        legend: {
            show: true,
        },
        tooltip: {
            linked: true,

            format: {
                value: (value, ratio, id) => {
                    return value + ' (' + (ratio * 100).toFixed(1) + '%)';
                },
            },
        },
    });

    BC19.setupBBGraph({
        bindto: '#test_results_graph',
        size: {
            height: BC19.graphSizes.STANDARD,
        },
        data: {
            x: 'date',
            colors: BC19.colors,
            columns: [
                graphData.dates,
                graphData.viralTests.newTests,
                graphData.viralTests.results,
            ],
            names: {
                new_tests: 'New Viral Tests',
                test_results: 'New Results',
            },
            types: {
                test_results: 'bar',
                new_tests: 'area-step',
            },
        },
        axis: {
            x: axisX,
            y: {
                max: BC19.getMaxY(maxValues.viralTests, tickCounts.STANDARD),
                padding: 0,
                tick: {
                    stepSize: BC19.getStepSize(maxValues.viralTests,
                                               tickCounts.STANDARD),
                },
            },
        },
        bar: {
            width: {
                ratio: 1.5,
            },
        },
        legend: {
            show: true,
        },
    });

    const testPosRateGraph = BC19.setupBBGraph({
        bindto: '#test_positivity_rate_graph',
        size: {
            height: BC19.graphSizes.STANDARD,
        },
        data: {
            x: 'date',
            colors: BC19.colors,
            columns: [
                graphData.dates,
                graphData.viralTests.testPositivityRate,
            ],
            names: {
                test_pos_rate: '7-Day Test Positivity Rate',
            },
            types: {
                test_pos_rate: 'area',
            },
        },
        axis: {
            x: axisX,
            y: {
                max: BC19.getMaxY(maxValues.sevenDayPosRate,
                                  tickCounts.STANDARD),
                padding: 0,
                tick: {
                    format: x => `${x.toFixed(1)}%`,
                    stepSize: BC19.getStepSize(maxValues.sevenDayPosRate,
                                               tickCounts.STANDARD),
                },
            },
        },
        tooltip: {
            format: {
                value: (value, ratio, id, index) => {
                    const fmtValue = `${value.toFixed(2)}%`;

                    if (index > 0) {
                        const prevValue =
                            testPosRateGraph.data(id)[0]
                            .values[index - 1].value;
                        const fmtRelValue =
                            Math.abs(value - prevValue).toFixed(2) + '%';

                        if (prevValue > value) {
                            return `${fmtValue} (-${fmtRelValue})`;
                        } else if (prevValue < value) {
                            return `${fmtValue} (+${fmtRelValue})`;
                        }
                    }

                    return fmtValue;
                },
            },
        },
    });

    const vaccineDosesPctDataMap = {};
    vaccineDosesPctDataMap[graphData.vaccines.firstDosesPct[0]] =
        graphData.vaccines.firstDoses;
    vaccineDosesPctDataMap[graphData.vaccines.fullDosesPct[0]] =
        graphData.vaccines.fullDoses;

    const vaccineDosesPctGraph = BC19.setupBBGraph({
        bindto: '#vaccines_doses',
        size: {
            height: BC19.graphSizes.STANDARD,
        },
        data: {
            x: 'date',
            colors: BC19.colors,
            columns: [
                graphData.dates,
                graphData.vaccines.firstDosesPct,
                graphData.vaccines.fullDosesPct,
            ],
            type: 'area-step',
            names: {
                vaccines_1st_dose_pct: 'Received 1 or More Doses',
                vaccines_full_doses_pct: 'Fully Vaccinated',
            },
        },
        axis: {
            x: axisX,
            y: {
                max: BC19.getMaxY(100, tickCounts.STANDARD),
                padding: 0,
                tick: {
                    format: x => `${x.toFixed(1)}%`,
                    stepSize: 25,
                },
            },
        },
        legend: {
            show: true,
        },
        tooltip: {
            format: {
                value: (value, ratio, id, index) => {
                    const fmtValue = `${value.toFixed(2)}%`;

                    if (index > 0) {
                        const prevValue =
                            vaccineDosesPctGraph.data(id)[0]
                            .values[index - 1].value;
                        const fmtRelValue =
                            Math.abs(value - prevValue).toFixed(2) + '%';
                        const relStr = (prevValue > value
                                        ? `-${fmtRelValue}`
                                        : `+${fmtRelValue}`);
                        const numPeople =
                            vaccineDosesPctDataMap[id][index + 1];
                        const prevNumPeople =
                            vaccineDosesPctDataMap[id][index];

                        let tooltip = `${fmtValue} (${relStr}) - ` +
                                      `${numPeople.toLocaleString()} people`;

                        if (numPeople > prevNumPeople) {
                            const relNumPeople =
                                (numPeople - prevNumPeople)
                                .toLocaleString();
                            tooltip += ` (+${relNumPeople})`;
                        }

                        return tooltip;
                    }

                    return fmtValue;
                },
            },
        },
    });

    const vaccineDosesGraph = BC19.setupBBGraph({
        bindto: '#vaccines_doses_by_day',
        size: {
            height: BC19.graphSizes.STANDARD,
        },
        data: {
            x: 'date',
            colors: BC19.colors,
            columns: [
                graphData.dates,
                graphData.vaccines.firstDoses,
                graphData.vaccines.fullDoses,
            ],
            type: 'area-step',
            names: {
                vaccines_1st_dose: 'Received 1 or More Doses',
                vaccines_full_doses: 'Fully Vaccinated',
            },
        },
        axis: {
            x: axisX,
            y: {
                max: BC19.getMaxY(maxValues.vaccinesAdministered,
                                  tickCounts.STANDARD),
                padding: 0,
                tick: {
                    stepSize: BC19.getStepSize(maxValues.vaccinesAdministered,
                                               tickCounts.STANDARD),
                },
            },
        },
        legend: {
            show: true,
        },
        tooltip: {
            format: {
                value: (value, ratio, id, index) => {
                    const fmtValue = value.toLocaleString();

                    if (index > 0) {
                        const prevValue =
                            vaccineDosesGraph.data(id)[0]
                            .values[index - 1].value;
                        const fmtRelValue =
                            Math.abs(value - prevValue).toLocaleString();
                        const relStr = (prevValue > value
                                        ? `-${fmtRelValue}`
                                        : `+${fmtRelValue}`);

                        return `${fmtValue} (${relStr})`;
                    }

                    return fmtValue;
                },
            },
        },
    });

    BC19.setupBBGraph({
        bindto: '#vaccines_one_week_rate_graph',
        size: {
            height: BC19.graphSizes.STANDARD,
        },
        data: {
            x: 'date',
            colors: BC19.colors,
            columns: [
                graphData.dates,
                graphData.vaccines.oneWeek1DoseRate,
                graphData.vaccines.oneWeekFullDosesRate,
            ],
            names: {
                vaccines_1st_dose_rate: '1+ Doses The Past 7 Days',
                vaccines_full_doses_rate: 'Fully-Vaccinated The Past 7 Days',
            },
            type: 'area',
        },
        axis: {
            x: axisX,
            y: {
                max: BC19.getMaxY(maxValues.oneWeekVaccinesRate,
                                  tickCounts.STANDARD),
                padding: 0,
                tick: {
                    stepSize: BC19.getStepSize(maxValues.oneWeekVaccinesRate,
                                               tickCounts.STANDARD),
                },
            },
        },
        legend: {
            show: true,
        },
        tooltip: {
            linked: true,
        },
    });

    const vaccineDosesByTypeGraph = BC19.setupBBGraph({
        bindto: '#vaccine_doses_by_type',
        size: {
            height: BC19.graphSizes.STANDARD,
        },
        data: {
            x: 'date',
            colors: BC19.colors,
            columns: [
                graphData.dates,
                graphData.vaccines.administeredJJ,
                graphData.vaccines.administeredModerna,
                graphData.vaccines.administeredPfizer,
            ],
            names: {
                vaccines_administered_jj: 'Johnson & Johnson',
                vaccines_administered_moderna: 'Moderna',
                vaccines_administered_pfizer: 'Pfizer',
                vaccines_administered_total: 'Total',
            },
            order: null,
            type: 'area-step',
        },
        axis: {
            x: axisX,
            y: {
                max: BC19.getMaxY(maxValues.vaccinesAdministeredByType,
                                  tickCounts.STANDARD),
                padding: 0,
                tick: {
                    stepSize: BC19.getStepSize(
                        maxValues.vaccinesAdministeredByType,
                        tickCounts.STANDARD),
                },
            },
        },
        legend: {
            show: true,
        },
        tooltip: {
            format: {
                value: (value, ratio, id, index) => {
                    const fmtValue = value.toLocaleString();

                    if (index > 0) {
                        const prevValue =
                            vaccineDosesByTypeGraph.data(id)[0]
                            .values[index - 1].value;
                        const fmtRelValue =
                            (value - prevValue).toLocaleString();

                        if (prevValue > value) {
                            return `${fmtValue} (-${fmtRelValue})`;
                        } else if (prevValue < value) {
                            return `${fmtValue} (+${fmtRelValue})`;
                        }
                    }

                    return fmtValue;
                },
            },
        },
    });

    const vaccinationsByGenderGraph = BC19.setupBBGraph({
        bindto: '#vaccines_by_gender',
        size: {
            height: BC19.graphSizes.STANDARD,
        },
        data: {
            x: 'date',
            colors: BC19.colors,
            columns: [
                graphData.dates,
                graphData.vaccines.gender.male,
                graphData.vaccines.gender.female,
                graphData.vaccines.gender.unknown,
            ],
            type: 'area-step',
            groups: [[
                'vaccines_male',
                'vaccines_female',
                'vaccines_unknown',
            ]],
            names: {
                vaccines_male: 'Male',
                vaccines_female: 'Female',
                vaccines_unknown: 'Unknown/undifferentiated',
            },
        },
        axis: {
            x: axisX,
            y: {
                max: BC19.getMaxY(100, tickCounts.STANDARD),
                padding: 0,
                tick: {
                    format: x => `${x.toFixed(1)}%`,
                    stepSize: 25,
                },
            },
        },
        legend: {
            show: true,
        },
        tooltip: {
            format: {
                value: (value, ratio, id, index) => {
                    const fmtValue = `${value.toFixed(2)}%`;

                    if (index > 0) {
                        const prevValue =
                            vaccinationsByGenderGraph.data(id)[0]
                            .values[index - 1].value;
                        const fmtRelValue =
                            Math.abs(value - prevValue).toFixed(2) + '%';
                        const relStr = (prevValue > value
                                        ? `-${fmtRelValue}`
                                        : `+${fmtRelValue}`);

                        return `${fmtValue} (${relStr})`;
                    }

                    return fmtValue;
                },
            },
        },
    });

    const vaccinationsByAgeGraph = BC19.setupBBGraph({
        bindto: '#vaccines_by_age',
        size: {
            height: BC19.graphSizes.STANDARD,
        },
        data: {
            x: 'date',
            colors: BC19.colors,
            columns: [
                graphData.dates,
                graphData.vaccines.age['0_11'],
                graphData.vaccines.age['12_17'],
                graphData.vaccines.age['18_49'],
                graphData.vaccines.age['50_64'],
                graphData.vaccines.age['65_plus'],
                graphData.vaccines.age.unknown,
            ],
            order: null,
            type: 'area-step',
            groups: [[
                'vaccines_0_11',
                'vaccines_12_17',
                'vaccines_18_49',
                'vaccines_50_64',
                'vaccines_65_plus',
                'vaccines_unknown',
            ]],
            names: {
                vaccines_0_11: '0-11',
                vaccines_12_17: '12-17',
                vaccines_18_49: '18-49',
                vaccines_50_64: '50-64',
                vaccines_65_plus: '65+',
                vaccines_unknown: 'Unknown',
            },
        },
        axis: {
            x: axisX,
            y: {
                max: BC19.getMaxY(100, tickCounts.STANDARD),
                padding: 0,
                tick: {
                    format: x => `${x.toFixed(1)}%`,
                    stepSize: 25,
                },
            },
        },
        legend: {
            show: true,
        },
        tooltip: {
            format: {
                value: (value, ratio, id, index) => {
                    const fmtValue = `${value.toFixed(2)}%`;

                    if (index > 0) {
                        const prevValue =
                            vaccinationsByAgeGraph.data(id)[0]
                            .values[index - 1].value;
                        const fmtRelValue =
                            Math.abs(value - prevValue).toFixed(2) + '%';
                        const relStr = (prevValue > value
                                        ? `-${fmtRelValue}`
                                        : `+${fmtRelValue}`);

                        return `${fmtValue} (${relStr})`;
                    }

                    return fmtValue;
                },
            },
        },
    });

    const vaccinationsByEthnicityGraph = BC19.setupBBGraph({
        bindto: '#vaccines_by_ethnicity',
        size: {
            height: BC19.graphSizes.STANDARD,
        },
        data: {
            x: 'date',
            colors: BC19.colors,
            columns: [
                graphData.dates,
                graphData.vaccines.ethnicity.aian,
                graphData.vaccines.ethnicity.asianAmerican,
                graphData.vaccines.ethnicity.black,
                graphData.vaccines.ethnicity.latino,
                graphData.vaccines.ethnicity.nhpi,
                graphData.vaccines.ethnicity.white,
                graphData.vaccines.ethnicity.multirace,
                graphData.vaccines.ethnicity.other,
                graphData.vaccines.ethnicity.unknown,
            ],
            type: 'area-step',
            groups: [[
                'vaccines_ai_an',
                'vaccines_asian_american',
                'vaccines_black',
                'vaccines_latino',
                'vaccines_white',
                'vaccines_nhpi',
                'vaccines_multirace',
                'vaccines_other',
                'vaccines_unknown',
            ]],
            names: {
                vaccines_ai_an: 'American Indian or Alaska Native',
                vaccines_asian_american: 'Asian American',
                vaccines_black: 'Black',
                vaccines_latino: 'Latino',
                vaccines_white: 'White',
                vaccines_nhpi: 'Native Hawaiian or Other Pacific Islander',
                vaccines_multirace: 'Multi-race',
                vaccines_other: 'Other',
                vaccines_unknown: 'Unknown',
            },
        },
        axis: {
            x: axisX,
            y: {
                max: BC19.getMaxY(100, tickCounts.STANDARD),
                padding: 0,
                tick: {
                    format: x => `${x.toFixed(1)}%`,
                    stepSize: 25,
                },
            },
        },
        legend: {
            show: true,
        },
        tooltip: {
            format: {
                value: (value, ratio, id, index) => {
                    const fmtValue = `${value.toFixed(2)}%`;

                    if (index > 0) {
                        const prevValue =
                            vaccinationsByEthnicityGraph.data(id)[0]
                            .values[index - 1].value;
                        const fmtRelValue =
                            Math.abs(value - prevValue).toFixed(2) + '%';
                        const relStr = (prevValue > value
                                        ? `-${fmtRelValue}`
                                        : `+${fmtRelValue}`);

                        return `${fmtValue} (${relStr})`;
                    }

                    return fmtValue;
                },
            },
        },
    });

    BC19.setupBBGraph({
        bindto: '#hospitalizations_icu_timeline_graph',
        size: {
            height: BC19.graphSizes.STANDARD,
        },
        data: {
            x: 'date',
            colors: BC19.colors,
            columns: [
                graphData.dates,
                graphData.hospitalizations.total,
                graphData.hospitalizations.icu,
            ],
            names: {
                hospitalizations: 'All Hospitalizations',
                icu: 'Just In ICU',
            },
            order: null,
            types: {
                cases: 'area-step',
                hospitalizations: 'area-step',
                icu: 'area-step',
            },
        },
        legend: {
            show: true,
        },
        axis: {
            x: axisX,
            y: {
                max: BC19.getMaxY(maxValues.hospitalizations,
                                  tickCounts.STANDARD),
                padding: 0,
                tick: {
                    stepSize: BC19.getStepSize(maxValues.hospitalizations,
                                               tickCounts.STANDARD),
                },
            },
        },
    });

    BC19.setupBBGraph({
        bindto: '#hospitalized_residents_timeline_graph',
        size: {
            height: BC19.graphSizes.STANDARD,
        },
        data: {
            x: 'date',
            colors: BC19.colors,
            columns: [
                graphData.dates,
                graphData.hospitalizations.residents,
            ],
            names: {
                residents: 'County Residents',
            },
            order: null,
            types: {
                residents: 'area-step',
            },
        },
        legend: {
            show: false,
        },
        axis: {
            x: axisX,
            y: {
                max: BC19.getMaxY(maxValues.hospitalizations,
                                  tickCounts.STANDARD),
                padding: 0,
                tick: {
                    stepSize: BC19.getStepSize(maxValues.hospitalizations,
                                               tickCounts.STANDARD),
                },
            },
        },
    });

    const maxIsolationValue =
        Math.max(isolationData.current[casesI + 1],
                 isolationData.released[casesI + 1],
                 graphData.cases.totalCases[casesI + 1]);
    BC19.setupBBGraph({
        bindto: '#isolation_timeline_graph',
        size: {
            height: BC19.graphSizes.STANDARD,
        },
        data: {
            x: 'date',
            colors: BC19.colors,
            columns: [
                graphData.dates,
                graphData.cases.totalCases,
                isolationData.current,
                isolationData.released,
            ],
            names: {
                cases: 'Confirmed Cases',
                in_isolation: 'Currently In Isolation',
                released_from_isolation: 'Total Released From Isolation',
            },
            order: null,
            types: {
                cases: 'area-step',
                in_isolation: 'area-step',
                released_from_isolation: 'area-step',
            },
        },
        legend: {
            show: true,
        },
        axis: {
            x: axisX,
            y: {
                max: BC19.getMaxY(maxIsolationValue, tickCounts.STANDARD),
                padding: 0,
                tick: {
                    stepSize: BC19.getStepSize(maxIsolationValue,
                                               tickCounts.STANDARD),
                },
            },
        },
    });

    const snfGraph = BC19.setupBBGraph({
        bindto: '#skilled_nursing_graph',
        size: {
            height: BC19.graphSizes.MEDIUM,
        },
        data: {
            x: 'date',
            colors: BC19.colors,
            columns: [
                graphData.dates,
                graphData.snf.curPatientCases,
                graphData.snf.curStaffCases,
            ],
            names: {
                current_patient_cases: 'Current Patient Cases',
                current_staff_cases: 'Current Staff Cases',
                total_patient_deaths: 'Total Patient Deaths',
                total_staff_deaths: 'Total Staff Deaths',
            },
            order: null,
            type: 'area-step',
            groups: [
                ['current_patient_cases', 'current_staff_cases'],
            ],
        },
        legend: {
            show: true,
        },
        tooltip: {
            format: {
                value: (value, ratio, id, index) => {
                    const fmtValue = `${value} or more`;

                    if (index > 0) {
                        const prevValue = snfGraph.data(id)[0]
                            .values[index - 1].value;
                        const fmtRelValue = Math.abs(value - prevValue);

                        if (prevValue > value) {
                            return `${fmtValue} (-${fmtRelValue})`;
                        } else if (prevValue < value) {
                            return `${fmtValue} (+${fmtRelValue})`;
                        }
                    }

                    return fmtValue;
                },
            },
        },
        axis: {
            x: axisX,
            y: {
                max: BC19.getMaxY(maxValues.snf, tickCounts.MEDIUM),
                padding: 0,
                tick: {
                    stepSize: BC19.getStepSize(maxValues.snf,
                                               tickCounts.MEDIUM),
                },
            },
        },
    });

    const snfDeathsGraph = BC19.setupBBGraph({
        bindto: '#skilled_nursing_deaths_graph',
        size: {
            height: BC19.graphSizes.SMALL,
        },
        data: {
            x: 'date',
            colors: BC19.colors,
            columns: [
                graphData.dates,
                graphData.snf.newPatientDeaths,
                graphData.snf.newStaffDeaths,
            ],
            names: {
                new_patient_deaths: 'New Patient Deaths',
                new_staff_deaths: 'New Staff Deaths',
            },
            order: null,
            types: {
                new_patient_deaths: 'bar',
                new_staff_deaths: 'bar',
            },
            groups: [
                ['new_patient_deaths', 'new_staff_deaths'],
            ],
        },
        legend: {
            show: true,
        },
        tooltip: {
            format: {
                value: (value, ratio, id, index) => {
                    const fmtValue = `${value} or more`;

                    if (index > 0) {
                        const prevValue = snfDeathsGraph.data(id)[0]
                            .values[index - 1].value;
                        const fmtRelValue = Math.abs(value - prevValue);

                        if (prevValue > value) {
                            return `${fmtValue} (-${fmtRelValue})`;
                        } else if (prevValue < value) {
                            return `${fmtValue} (+${fmtRelValue})`;
                        }
                    }

                    return fmtValue;
                },
            },
        },
        axis: {
            x: axisX,
            y: {
                max: BC19.getMaxY(maxValues.newSNFDeaths, tickCounts.SMALL),
                padding: 0,
                tick: {
                    stepSize: BC19.getStepSize(maxValues.newSNFDeaths,
                                               tickCounts.SMALL),
                },
            },
        },
    });

    const adultSeniorCareGraph = BC19.setupBBGraph({
        bindto: '#adult_senior_care_graph',
        size: {
            height: BC19.graphSizes.MEDIUM,
        },
        data: {
            x: 'date',
            colors: BC19.colors,
            columns: [
                graphData.dates,
                graphData.adultSeniorCare.curPatientCases,
                graphData.adultSeniorCare.curStaffCases,
            ],
            names: {
                current_patient_cases: 'Current Patient Cases',
                current_staff_cases: 'Current Staff Cases',
                total_patient_deaths: 'Total Patient Deaths',
                total_staff_deaths: 'Total Staff Deaths',
            },
            order: null,
            type: 'area-step',
            groups: [
                ['current_patient_cases', 'current_staff_cases'],
            ],
        },
        legend: {
            show: true,
        },
        tooltip: {
            format: {
                value: (value, ratio, id, index) => {
                    const fmtValue = `${value} or more`;

                    if (index > 0) {
                        const prevValue = adultSeniorCareGraph.data(id)[0]
                            .values[index - 1].value;
                        const fmtRelValue = Math.abs(value - prevValue);

                        if (prevValue > value) {
                            return `${fmtValue} (-${fmtRelValue})`;
                        } else if (prevValue < value) {
                            return `${fmtValue} (+${fmtRelValue})`;
                        }
                    }

                    return fmtValue;
                },
            },
        },
        axis: {
            x: axisX,
            y: {
                max: BC19.getMaxY(maxValues.adultSeniorCareCases,
                                  tickCounts.MEDIUM),
                padding: 0,
                tick: {
                    stepSize: BC19.getStepSize(maxValues.adultSeniorCareCases,
                                               tickCounts.MEDIUM),
                },
            },
        },
    });

    const adultSeniorCareDeathsGraph = BC19.setupBBGraph({
        bindto: '#adult_senior_care_deaths_graph',
        size: {
            height: BC19.graphSizes.SMALL,
        },
        data: {
            x: 'date',
            colors: BC19.colors,
            columns: [
                graphData.dates,
                graphData.adultSeniorCare.newPatientDeaths,
                graphData.adultSeniorCare.newStaffDeaths,
            ],
            names: {
                new_patient_deaths: 'New Patient Deaths',
                new_staff_deaths: 'New Staff Deaths',
            },
            order: null,
            types: {
                new_patient_deaths: 'bar',
                new_staff_deaths: 'bar',
            },
            groups: [
                ['new_patient_deaths', 'new_staff_deaths'],
            ],
        },
        legend: {
            show: true,
        },
        tooltip: {
            format: {
                value: (value, ratio, id, index) => {
                    const fmtValue = `${value} or more`;

                    if (index > 0) {
                        const prevValue =
                            adultSeniorCareDeathsGraph.data(id)[0]
                            .values[index - 1].value;
                        const fmtRelValue = Math.abs(value - prevValue);

                        if (prevValue > value) {
                            return `${fmtValue} (-${fmtRelValue})`;
                        } else if (prevValue < value) {
                            return `${fmtValue} (+${fmtRelValue})`;
                        }
                    }

                    return fmtValue;
                },
            },
        },
        axis: {
            x: axisX,
            y: {
                max: BC19.getMaxY(maxValues.newAdultSeniorCareDeaths,
                                  tickCounts.SMALL),
                padding: 0,
                tick: {
                    stepSize: BC19.getStepSize(
                        maxValues.newAdultSeniorCareDeaths,
                        tickCounts.SMALL),
                },
            },
        },
    });

    const maxInmateCasesValue = Math.max(maxValues.jailInmateCurCases,
                                         maxValues.jailInmatePopulation);
    BC19.setupBBGraph({
        bindto: '#jail_inmates_cur_cases_timeline_graph',
        size: {
            height: BC19.graphSizes.STANDARD,
        },
        data: {
            x: 'date',
            colors: BC19.colors,
            columns: [
                graphData.dates,
                graphData.jail.inmatePopulation,
                graphData.jail.inmateCurCases,
            ],
            order: null,
            names: {
                jail_inmate_cur_cases: 'Current Inmate Cases',
                jail_inmate_pop: 'Inmate Population',
            },
            types: {
                jail_inmate_cur_cases: 'area-step',
                jail_inmate_pop: 'area-step',
            },
        },
        legend: {
            show: true,
        },
        axis: {
            x: axisX,
            y: {
                max: BC19.getMaxY(maxInmateCasesValue, tickCounts.STANDARD),
                padding: 0,
                tick: {
                    stepSize: BC19.getStepSize(maxInmateCasesValue,
                                               tickCounts.STANDARD),
                },
            },
        },
    });

    BC19.setupBBGraph({
        bindto: '#jail_staff_total_cases_timeline_graph',
        size: {
            height: BC19.graphSizes.SMALL,
        },
        data: {
            x: 'date',
            colors: BC19.colors,
            columns: [
                graphData.dates,
                graphData.jail.staffTotalCases,
            ],
            names: {
                jail_staff_total_cases: 'Total Staff Cases',
            },
            type: 'area-step',
        },
        axis: {
            x: axisX,
            y: {
                max: BC19.getMaxY(maxValues.jailStaffTotalCases,
                                  tickCounts.SMALL),
                padding: 0,
                tick: {
                    stepSize: BC19.getStepSize(maxValues.jailStaffTotalCases,
                                               tickCounts.SMALL),
                },
            },
        },
    });
};


/**
 * Initialize the page.
 *
 * This will begin loading the timeline data for the page. Once loaded, it
 * will be parsed, and then all counters and graphs will be set to render
 * the data.
 *
 * Any errors encountered will result in a log message and an alert.
 */
BC19.init = function() {
    BC19.loadDashboard(
        'data/json/bc19-dashboard.1.min.json',
        dashboardData => {
            BC19.processDashboardData(dashboardData);
            BC19.setupElements();

            setupCounters();
            setupBarGraphs();
            setupTimelineGraphs();

            BC19.renderNextGraphData();
        });
};
