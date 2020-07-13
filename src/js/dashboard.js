window.BC19 = {
    COUNTY_POPULATION: 219186,

    stepSizes: {
        TOTAL_CASES: 40,
        NEW_CASES: 10,
        DEATHS: 2,
        TOTAL_TESTS: 200,
        DEMOGRAPHICS: 50,
        HOSPITALIZATIONS: 2,
        ISOLATION: 50,
        SNF: 2,
        TEST_POSITIVITY_RATE: 2,
    },

    minDates: {
        testPositivityRate: '2020-04-10',
    },

    maxValues: {
        newCases: 0,
        newDeaths: 0,
        hospitalizations: 0,
    },

    graphSizes: {
        VERY_TALL: 380,
        STANDARD: 240,
        MEDIUM: 200,
        SMALL: 120,
        VERY_SMALL: 120,
    },

    colors: {
        cases: '#4783EF',
        new_cases: '#E86050',
        new_deaths: '#981000',

        neg_results: '#A8D6F1',
        pos_results: '#D85040',
        new_tests: '#C7DAFA',
        test_results: '#3BA859',
        test_pos_rate: '#883333',

        in_isolation: '#DD0000',
        released_from_isolation: '#3BA859',

        hospitalizations: '#C783EF',
        icu: '#87063B',
        residents: '#0000FF',

        chico: '#4783EF',
        oroville: '#E7463B',
        gridley: '#3BA859',
        other: '#F9BD34',

        age_0_17: '#4783EF',
        age_18_49: '#E7463B',
        age_50_64: '#3BA859',
        age_65_plus: '#F9BD34',

        current_patient_cases: '#D0A9D9',
        current_staff_cases: '#8FC3E7',
    },

    els: {
    },

    ageRangeInfo: {
        '0_17': {sourceKey: '0-17'},
        '18_24': {sourceKey: '18-24'},
        '25_34': {sourceKey: '25-34'},
        '35_44': {sourceKey: '35-44'},
        '45_54': {sourceKey: '45-54'},
        '55_64': {sourceKey: '55-64'},
        '65_74': {sourceKey: '65-74'},
        '75_plus': {
            text: '75+',
            sourceKey: '75_plus',
        },

        // Legacy data, unpublished as of July 9, 2020.
        '18-49': {
            legacy: true,
            sourceKey: '18-49',
        },
        '50-64': {
            legacy: true,
            sourceKey: '50-64',
        },
        '65_plus': {
            legacy: true,
            text: '65+',
            sourceKey: '65_plus',
        },
    },
    allAgeRanges: [],
    visibleAgeRanges: [],

    graphs: [],
    graphsData: {},
    graphZoomGroups: {},
    zoomingGraphs: {},
    latestCasesRow: null,
    latestStateDataRow: null,
    latestPerHospitalDataRow: null,
    commonTimelineOptions: {
        bar: {
            radius: {
                ratio: 0.3,
            },
        },
        grid: {
            y: {
                show: true,
            },
        },
        legend: {
            show: false,
        },
        tooltip: {
            linked: true,
        },
        padding: {
            right: 10,
        },
        svg: {
            classname: 'bb-graph-svg',
        },
    },

    defaultTimelineDomain: null,
};


BC19.parseMDate = function(dateStr) {
    return moment(dateStr + ' -0700', 'YYYY-MM-DD Z');
};


BC19.formatMDate = function(mDate) {
    return mDate.format('LL');
};


BC19.getDayText = function(date) {
    const days = moment().diff(date, 'days');

    if (days === 0) {
        return 'today';
    } else if (days === 1) {
        return 'yesterday';
    } else {
        return moment(date).format('dddd');
    }
};


BC19.processTimelineData = function(timeline) {
    const rows = timeline.dates;
    const graphDates = ['date'];

    const graphTotalCases = ['cases'];
    const graphNewCases = ['new_cases'];
    const graphNewDeaths = ['new_deaths'];

    const graphTotalTests = ['total_tests'];
    const graphNewTests = ['new_tests'];
    const graphTotalTestResults = ['test_results'];
    const graphNegativeResults = ['neg_results'];
    const graphPositiveResults = ['pos_results'];
    const graphTestPositivityRate = ['test_pos_rate'];

    const graphCasesInChico = ['chico'];
    const graphCasesInGridley = ['gridley'];
    const graphCasesInOroville = ['oroville'];
    const graphCasesInOtherRegion = ['other'];

    const ageRangeInfo = BC19.ageRangeInfo;
    const ageRangeKeys = Object.keys(ageRangeInfo);
    const graphCasesByAge = {};
    const graphCasesByAge0_17 = ['age_0_17'];
    const graphCasesByAge18_24 = ['age_18_24'];
    const graphCasesByAge25_34 = ['age_25_34'];
    const graphCasesByAge35_44 = ['age_35_44'];
    const graphCasesByAge45_54 = ['age_45_54'];
    const graphCasesByAge55_64 = ['age_55_64'];
    const graphCasesByAge65_74 = ['age_65_74'];
    const graphCasesByAge75Plus = ['age_75_plus'];
    const graphCasesByAge18_49 = ['age_18_49'];
    const graphCasesByAge50_64 = ['age_50_64'];
    const graphCasesByAge65Plus = ['age_65_plus'];

    const graphInIsolation = ['in_isolation'];
    const graphReleasedFromIsolation = ['released_from_isolation'];

    const graphHospitalizations = ['hospitalizations'];
    const graphICU = ['icu'];
    const graphHospitalizedResidents = ['residents'];

    const graphNursingCurPatientCases = ['current_patient_cases'];
    const graphNursingCurStaffCases = ['current_staff_cases'];
    const graphNursingTotalPatientDeaths = ['total_patient_deaths'];
    const graphNursingTotalStaffDeaths = ['total_staff_deaths'];

    const graphNotes = [];

    let maxNewCases = 0;
    let maxNewDeaths = 0;
    let maxHospitalizationsY = 0;

    let latestCasesRow;
    let latestStateDataRow;
    let latestPerHospitalDataRow;

    const minTestPositivityRateDate = BC19.minDates.testPositivityRate;
    let foundMinTestPositivityRateDate = false;

    ageRangeKeys.forEach(key => {
        graphCasesByAge[key] = [`age_${key.replace('-', '_')}`];
    });

    for (let i = 0; i < rows.length; i++) {
        const row = rows[i];

        row.i = i;

        const confirmedCases = row.confirmed_cases;
        const deltaConfirmedCases = Math.max(confirmedCases.delta_total, 0);
        const viralTests = row.viral_tests;
        const viralTestResults = viralTests.results;
        const regions = row.regions;
        const ageRanges = row.age_ranges_in_years;
        const countyHospital = row.hospitalizations.county_data;
        const stateHospital = row.hospitalizations.state_data;
        const snf = row.skilled_nursing_facilities;

        graphDates.push(row.date);
        graphTotalCases.push(confirmedCases.total);
        graphNewCases.push(deltaConfirmedCases);
        graphNewDeaths.push(row.deaths.delta_total);

        graphTotalTests.push(viralTests.total);
        graphNewTests.push(viralTests.delta_total || 0);
        graphTotalTestResults.push(viralTests.results || 0);

        if (viralTestResults !== null && deltaConfirmedCases !== null) {
            graphNegativeResults.push(viralTestResults - deltaConfirmedCases);
            graphPositiveResults.push(deltaConfirmedCases);
        } else {
            graphNegativeResults.push(0);
            graphPositiveResults.push(0);
        }

        graphCasesInChico.push(regions.chico.cases);
        graphCasesInOroville.push(regions.oroville.cases);
        graphCasesInGridley.push(regions.gridley.cases);
        graphCasesInOtherRegion.push(regions.other.cases);

        ageRangeKeys.forEach(key => {
            graphCasesByAge[key].push(ageRanges[ageRangeInfo[key].sourceKey]);
        });

        graphInIsolation.push(row.in_isolation.current || 0);
        graphReleasedFromIsolation.push(row.in_isolation.total_released || 0);

        graphHospitalizations.push(stateHospital.positive || 0);
        graphICU.push(stateHospital.icu_positive || 0);
        graphHospitalizedResidents.push(countyHospital.hospitalized || 0);

        maxHospitalizationsY = Math.max(maxHospitalizationsY,
                                        stateHospital.positive,
                                        countyHospital.hospitalized);

        graphNursingCurPatientCases.push(snf.current_patient_cases);
        graphNursingCurStaffCases.push(snf.current_staff_cases);
        graphNursingTotalPatientDeaths.push(snf.total_patient_deaths);
        graphNursingTotalStaffDeaths.push(snf.total_staff_deaths);

        if (!foundMinTestPositivityRateDate &&
            row.date === minTestPositivityRateDate) {
            foundMinTestPositivityRateDate = true;
        }

        const sevenDaysAgo = rows[i - 7];

        if (foundMinTestPositivityRateDate &&
            confirmedCases.total !== null &&
            viralTests.total !== null &&
            sevenDaysAgo.confirmed_cases.total !== null &&
            sevenDaysAgo.viral_tests.total !== null) {
            graphTestPositivityRate.push(
                (confirmedCases.total - sevenDaysAgo.confirmed_cases.total) /
                (viralTests.total - sevenDaysAgo.viral_tests.total) *
                100.0);
        } else {
            graphTestPositivityRate.push(null);
        }

        maxNewDeaths = Math.max(maxNewDeaths, row.deaths.delta_total);

        if (deltaConfirmedCases && deltaConfirmedCases > maxNewCases) {
            maxNewCases = confirmedCases.delta_total;
        }

        if (row.note) {
            graphNotes.push({
                value: row.date,
                text: row.note,
            });
        }

        if (confirmedCases.total !== null) {
            latestCasesRow = row;
        }

        const stateData = row.hospitalizations.state_data;

        if (stateData.positive !== null) {
            latestStateDataRow = row;
        }

        if (stateData.enloe_hospital !== null) {
            latestPerHospitalDataRow = row;
        }
    }

    if (latestCasesRow === null) {
        throw new Error(
            "Oh no! The latest COVID-19 case data couldn't be " +
            "found! Please report this :)");
    }

    if (latestStateDataRow === null) {
        throw new Error(
            "Oh no! The latest COVID-19 hospitals data couldn't be " +
            "found! Please report this :)");
    }

    BC19.latestCasesRow = latestCasesRow;
    BC19.latestStateDataRow = latestStateDataRow;
    BC19.latestPerHospitalDataRow = latestPerHospitalDataRow;
    BC19.firstMDate = BC19.parseMDate(timeline.dates[0].date);
    BC19.lastMDate = BC19.parseMDate(timeline.dates[rows.length - 1].date);
    BC19.timeline = timeline;

    BC19.allAgeRanges = ageRangeKeys;
    BC19.visibleAgeRanges = ageRangeKeys.filter(
        key => !BC19.ageRangeInfo[key].legacy);

    BC19.defaultTimelineDomain = [
        moment(BC19.lastMDate).subtract(90, 'days').format('YYYY-MM-DD'),
        BC19.lastMDate.format('YYYY-MM-DD'),
    ];

    BC19.maxValues = {
        newCases: maxNewCases,
        newDeaths: maxNewDeaths,
        totalCases: latestCasesRow.confirmed_cases.total,
        hospitalizations: maxHospitalizationsY,
    };

    BC19.graphData = {
        dates: graphDates,
        notes: graphNotes,
        deaths: {
            newDeaths: graphNewDeaths,
        },
        cases: {
            totalCases: graphTotalCases,
            newCases: graphNewCases,
        },
        viralTests: {
            total: graphTotalTests,
            results: graphTotalTestResults,
            newTests: graphNewTests,
            negativeResults: graphNegativeResults,
            positiveResults: graphPositiveResults,
            testPositivityRate: graphTestPositivityRate,
        },
        regions: {
            chico: graphCasesInChico,
            oroville: graphCasesInOroville,
            gridley: graphCasesInGridley,
            other: graphCasesInOtherRegion,
        },
        ageRanges: graphCasesByAge,
        isolation: {
            current: graphInIsolation,
            released: graphReleasedFromIsolation,
        },
        hospitalizations: {
            total: graphHospitalizations,
            icu: graphICU,
            residents: graphHospitalizedResidents,
        },
        snf: {
            curPatientCases: graphNursingCurPatientCases,
            curStaffCases: graphNursingCurStaffCases,
            totalPatientDeaths: graphNursingTotalPatientDeaths,
            totalStaffDeaths: graphNursingTotalStaffDeaths,
        },
    };
};


BC19.setupBBGraph = function(options) {
    options = Object.assign({}, BC19.commonTimelineOptions, options);

    const graph = bb.generate(options);
    BC19.graphs.push(graph);

    if (!options.tooltip || !options.tooltip.format) {
        graph.config(
            'tooltip.format.value',
            function(_graph, value, ratio, id, index) {
                if (index > 0) {
                    const prevValue =
                        _graph.data(id)[0].values[index - 1].value;

                    if (prevValue > value) {
                        return value + ' (-' + (prevValue - value) + ')';
                    } else if (prevValue < value) {
                        return value + ' (+' + (value - prevValue) + ')';
                    }
                }

                return value;
            }.bind(this, graph));
    }

    return graph;
};


BC19.setupBarGraph = function(graph, options, data) {
    const showPct = options && !!options.pct;

    const total = d3.sum(data, d => d.value);
    const x = d3.scaleLinear()
        .domain([0, d3.max(data, d => d.value)])
        .range([0, 100]);

    const rows = graph
        .selectAll('.bc19-c-bar-graph__group')
        .data(data)
        .enter()
        .select(function(d) {
            this.appendChild(d3.create('label')
                .attr('class', 'bc19-c-bar-graph__label')
                .attr('for', 'bar_graph_' + d.data_id)
                .text(d.label)
                .node());

            this.appendChild(d3.create('div')
                .attr('class', 'bc19-c-bar-graph__bar')
                .attr('id', 'bar_graph_' + d.data_id)
                .style('width', x(d.value) + '%')
                .text(showPct
                      ? d.value + '  ' +
                        Math.round((d.value / total) * 100) + '%'
                      : d.value)
                .node());

            let relValue = '';
            let relClass = '';
            let relTitle;

            if (d.relValue > 0) {
                relValue = d.relValue;
                relClass = '-is-up';
                relTitle = '+' + relValue + ' since yesterday';
            } else if (d.relValue < 0) {
                relValue = -d.relValue;
                relClass = '-is-down';
                relTitle = '-' + relValue + ' since yesterday';
            }

            this.appendChild(d3.create('span')
                .attr('class', 'bc19-c-bar-graph__rel-value ' + relClass)
                .attr('title', relTitle)
                .text(relValue)
                .node());
        });
};


BC19.setCounter = function(el, options) {
    const value = options.value;
    const formatValue = options.formatValue || function(value) {
        return value.toLocaleString();
    };

    el.querySelector('.bc19-c-counter__value').innerText = formatValue(value);

    const relValues = options.relativeValues;

    if (relValues && relValues.length > 0) {
        const relativeValueEls =
            el.querySelectorAll('.bc19-c-counter__relative-value');
        console.assert(relativeValueEls.length === relValues.length);

        for (let i = 0; i < relValues.length; i++) {
            const relValueEl = relativeValueEls[i];
            const relEl = relValueEl.parentNode;
            const relValue = relValues[i];
            const formatRelValue =
                options.formatRelValues
                ? options.formatRelValues[i]
                : (value, relValue) => Math.abs(value - relValue);

            relValueEl.innerText = formatRelValue(value, relValue);
            relEl.classList.remove('-is-up');
            relEl.classList.remove('-is-down');
            relEl.classList.remove('-is-unchanged');

            if (relValue > value) {
                relEl.classList.add('-is-down');
            } else if (relValue < value) {
                relEl.classList.add('-is-up');
            } else {
                relEl.classList.add('-is-unchanged');
            }
        }
    }
};


BC19.setupCounters = function(timeline) {
    const dates = timeline.dates;
    const casesRow = BC19.latestCasesRow;
    const hospitalsRow = BC19.latestStateDataRow;
    const casesI = casesRow.i;
    const hospitalsI = hospitalsRow.i;

    const curCasesTotal = casesRow.confirmed_cases.total;
    const totalTests = casesRow.viral_tests.total;

    BC19.setCounter(
        document.getElementById('total-cases-counter'),
        {
            value: curCasesTotal,
            relativeValues: [
                dates[casesI - 1].confirmed_cases.total,
                dates[casesI - 7].confirmed_cases.total,
                dates[casesI - 14].confirmed_cases.total,
                dates[casesI - 30].confirmed_cases.total,
            ],
        });

    BC19.setCounter(
        document.getElementById('deaths-counter'),
        {
            value: casesRow.deaths.total,
            relativeValues: [
                dates[casesI - 1].deaths.total,
            ],
        });

    BC19.setCounter(
        document.getElementById('in-isolation-counter'),
        {
            value: casesRow.in_isolation.current,
            relativeValues: [
                dates[casesI - 1].in_isolation.current,
            ],
        });

    BC19.setCounter(
        document.getElementById('hospitalized-residents-counter'),
        {
            value: casesRow.hospitalizations.county_data.hospitalized,
            relativeValues: [
                dates[casesI - 1].hospitalizations.county_data.hospitalized,
            ],
        });

    BC19.setCounter(
        document.getElementById('hospitalized-counter'),
        {
            value: hospitalsRow.hospitalizations.state_data.positive,
            relativeValues: [
                dates[hospitalsI - 1].hospitalizations.state_data.positive,
            ],
        });

    BC19.setCounter(
        document.getElementById('icu-counter'),
        {
            value: hospitalsRow.hospitalizations.state_data.icu_positive,
            relativeValues: [
                dates[hospitalsI - 1].hospitalizations.state_data.icu_positive,
            ],
        });

    BC19.setCounter(
        document.getElementById('total-tests-counter'),
        {
            value: totalTests,
            relativeValues: [
                dates[casesI - 1].viral_tests.total,
            ],
        });

    BC19.setCounter(
        document.getElementById('positive-test-results-counter'),
        {
            value: curCasesTotal,
            relativeValues: [
                dates[casesI - 1].confirmed_cases.total,
            ],
        });

    BC19.setCounter(
        document.getElementById('positive-test-rate-counter'),
        {
            value: BC19.graphData.viralTests.testPositivityRate[casesI + 1],
            relativeValues: [
                BC19.graphData.viralTests.testPositivityRate[casesI],
            ],
            formatValue: value => value.toFixed(2) + '%',
            formatRelValues: [
                (value, relValue) => {
                    return Math.abs(value - relValue).toFixed(2) + '%';
                },
            ],
        });

    BC19.setCounter(
        document.getElementById('county-population-counter'),
        {
            value: BC19.COUNTY_POPULATION,
        });

    BC19.setCounter(
        document.getElementById('pop-tested-pct-counter'),
        {
            value: (totalTests / BC19.COUNTY_POPULATION * 100).toFixed(2),
            formatValue: value => '< ' + value + '%',
        });

    BC19.setCounter(
        document.getElementById('pop-not-tested-pct-counter'),
        {
            value: (totalTests / BC19.COUNTY_POPULATION * 100).toFixed(2),
            formatValue: value => '> ' + (100 - value) + '%',
        });

    document.getElementById('pop-tested-pct-counter-people').innerText =
        totalTests.toLocaleString();
    document.getElementById('pop-not-tested-pct-counter-people').innerText =
        (BC19.COUNTY_POPULATION - totalTests).toLocaleString();
};


BC19.forEachGraphAsync = function(cb) {
    BC19.graphs.forEach(graph => {
        requestAnimationFrame(() => cb(graph));
    });
};


BC19.setupByAgeGraph = function(timeline) {
    /*
     * XXX This is temporary while we're still dealing with the transition
     *     to finer-segmented age ranges.
     */
    const hasPrev = (BC19.latestCasesRow.date != '2020-07-09');
    const casesI = BC19.latestCasesRow.i + 1;

    BC19.setupBarGraph(
        d3.select('#by_age_graph'),
        {},
        BC19.visibleAgeRanges.map(key => {
            const ageRanges = BC19.graphData.ageRanges[key];
            const ageRangeInfo = BC19.ageRangeInfo[key];
            const value = ageRanges[casesI];
            const prevValue = ageRanges[casesI - 1];

            return {
                data_id: key,
                label: ageRangeInfo.text || key.replace('_', '-'),
                value: value,
                relValue: value - (hasPrev ? ageRanges[casesI - 1] : value),
            };
        }));
};


BC19.setupByRegionGraph = function(timeline) {
    const regions = BC19.latestCasesRow.regions;
    const prevIndex = BC19.latestCasesRow.i - 1;
    const prevRegions = timeline.dates[prevIndex].regions;

    BC19.setupBarGraph(
        d3.select('#by_region_graph'),
        {},
        [
            {
                data_id: 'chico',
                label: 'Chico',
                value: regions.chico.cases,
                relValue: regions.chico.cases - prevRegions.chico.cases,
            },
            {
                data_id: 'oroville',
                label: 'Oroville',
                value: regions.oroville.cases,
                relValue: regions.oroville.cases - prevRegions.oroville.cases,
            },
            {
                data_id: 'gridley',
                label: 'Gridley',
                value: regions.gridley.cases,
                relValue: regions.gridley.cases - prevRegions.gridley.cases,
            },
            {
                data_id: 'other',
                label: 'Other',
                value: regions.other.cases,
                relValue: regions.other.cases - prevRegions.other.cases,
            },
        ]);
};


BC19.setupByHospitalGraph = function(timeline) {
    const dateInfo = BC19.latestPerHospitalDataRow;
    const prevIndex = BC19.latestPerHospitalDataRow.i - 1;
    const data = dateInfo.hospitalizations.state_data;
    const prevData = timeline.dates[prevIndex].hospitalizations.state_data;

    BC19.setupBarGraph(
        d3.select('#by_hospital_graph'),
        {},
        [
            {
                data_id: 'enloe',
                label: 'Enloe Hospital',
                value: data.enloe_hospital,
                relValue: data.enloe_hospital - prevData.enloe_hospital,
            },
            {
                data_id: 'oroville',
                label: 'Oroville Hospital',
                value: data.oroville_hospital,
                relValue: data.oroville_hospital - prevData.oroville_hospital,
            },
            {
                data_id: 'orchard',
                label: 'Orchard Hospital',
                value: data.orchard_hospital,
                relValue: data.orchard_hospital - prevData.orchard_hospital,
            },
        ]);
};


BC19.setupMainTimelineGraphs = function(timeline) {
    const maxValues = BC19.maxValues;
    const totalCaseStepCount = BC19.stepSizes.TOTAL_CASES;
    const newCaseStepCount = BC19.stepSizes.NEW_CASES;
    const deathsStepCount = BC19.stepSizes.DEATHS;
    const casesRow = BC19.latestCasesRow;
    const casesI = casesRow.i;

    const axisX = {
        type: 'timeseries',
        localtime: false,
        label: {
            position: 'outer-left',
        },
        tick: {
            fit: false,
            format: '%B %d',
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
            columns: [BC19.graphData.dates, BC19.graphData.cases.totalCases],
            names: {
                cases: 'Total Cases',
            },
            types: {
                cases: 'bar',
            },
        },
        grid: {
            x: {
                lines: BC19.graphData.notes,
            },
            y: {
                show: true,
            },
        },
        axis: {
            x: axisX,
            y: {
                padding: 120,
                max: Math.ceil(BC19.maxTotalCases / totalCaseStepCount) *
                     totalCaseStepCount,
                tick: {
                    stepSize: totalCaseStepCount,
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
            columns: [BC19.graphData.dates, BC19.graphData.cases.newCases],
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
                max: Math.ceil(maxValues.newCases / newCaseStepCount) *
                     newCaseStepCount,
                padding: 0,
                tick: {
                    stepSize: newCaseStepCount,
                },
            },
        },
    });

    BC19.setupBBGraph({
        bindto: '#deaths_graph',
        size: {
            height: BC19.graphSizes.SMALL,
        },
        data: {
            x: 'date',
            colors: BC19.colors,
            columns: [BC19.graphData.dates, BC19.graphData.deaths.newDeaths],
            names: {
                new_deaths: 'Deaths',
            },
            types: {
                new_deaths: 'bar',
            },
        },
        axis: {
            x: axisX,
            y: {
                max: Math.ceil(maxValues.newDeaths / deathsStepCount) *
                     deathsStepCount,
                padding: 0,
                tick: {
                    stepSize: deathsStepCount,
                },
            },
        },
    });

    BC19.setupBBGraph({
        bindto: '#cases_by_age_timeline_graph',
        size: {
            height: BC19.graphSizes.STANDARD,
        },
        data: {
            x: 'date',
            colors: BC19.colors,
            columns: [
                BC19.graphData.dates,
            ].concat(Object.values(BC19.graphData.ageRanges)),
            names: {
                age_0_17: '0-17 Years',
                age_18_24: '18-24',
                age_25_34: '25-34',
                age_35_44: '35-44',
                age_45_54: '45-54',
                age_55_64: '55-64',
                age_65_74: '65-74',
                age_75_plus: '75+',

                age_18_49: '18-49',
                age_50_64: '50-64',
                age_65_plus: '65+',
            },
            order: null,
            types: {
                age_0_17: 'bar',
                age_18_24: 'bar',
                age_25_34: 'bar',
                age_35_44: 'bar',
                age_45_54: 'bar',
                age_55_64: 'bar',
                age_65_74: 'bar',
                age_75_plus: 'bar',

                age_18_49: 'bar',
                age_50_64: 'bar',
                age_65_plus: 'bar',
            },
            groups: [
                [
                    'age_0_17',
                    'age_18_24',
                    'age_25_34',
                    'age_35_44',
                    'age_45_54',
                    'age_55_64',
                    'age_65_74',
                    'age_75_plus',

                    'age_18_49',
                    'age_50_64',
                    'age_65_plus',
                ],
            ],
        },
        axis: {
            x: axisX,
            y: {
                tick: {
                    stepSize: BC19.stepSizes.DEMOGRAPHICS,
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
            height: BC19.graphSizes.STANDARD,
        },
        data: {
            x: 'date',
            colors: BC19.colors,
            columns: [
                BC19.graphData.dates,
                BC19.graphData.regions.chico,
                BC19.graphData.regions.oroville,
                BC19.graphData.regions.gridley,
                BC19.graphData.regions.other,
            ],
            names: {
                chico: 'Chico',
                oroville: 'Oroville',
                gridley: 'Gridley',
                other: 'Other',
            },
            order: null,
            types: {
                chico: 'bar',
                oroville: 'bar',
                gridley: 'bar',
                other: 'bar',
            },
            groups: [
                ['oroville', 'gridley', 'other', 'chico'],
            ],
        },
        axis: {
            x: axisX,
            y: {
                tick: {
                    stepSize: BC19.stepSizes.DEMOGRAPHICS,
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
                BC19.graphData.dates,
                BC19.graphData.viralTests.negativeResults,
                BC19.graphData.viralTests.positiveResults,
            ],
            groups: [['neg_results', 'pos_results']],
            names: {
                neg_results: 'Negative Test Results',
                pos_results: 'Positive Test Results',
            },
            stack: {
                normalize: true,
            },
            types: {
                neg_results: 'bar',
                pos_results: 'bar',
            },
        },
        axis: {
            x: axisX,
            y: {
                tick: {
                    stepSize: 25,
                },
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
                BC19.graphData.dates,
                BC19.graphData.viralTests.newTests,
                BC19.graphData.viralTests.results,
            ],
            names: {
                new_tests: 'New Viral Tests',
                test_results: 'New Results',
            },
            types: {
                test_results: 'bar',
                new_tests: 'bar',
            },
        },
        axis: {
            x: axisX,
            y: {
                tick: {
                    stepSize: BC19.stepSizes.TOTAL_TESTS,
                },
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
                BC19.graphData.dates,
                BC19.graphData.viralTests.testPositivityRate,
            ],
            names: {
                test_pos_rate: 'Test Positivity Rate',
            },
            types: {
                test_pos_rate: 'area',
            },
        },
        axis: {
            x: axisX,
            y: {
                max: Math.max(
                    10,
                    BC19.graphData.viralTests.testPositivityRate[casesI + 1]),
                tick: {
                    stepSize: BC19.stepSizes.TEST_POSITIVITY_RATE,
                    format: x => `${x.toFixed(1)}%`,
                },
            },
        },
        grid: {
            y: {
                lines: [
                    {
                        value: 8,
                        text: 'May qualify to be on a monitoring list at 8%',
                        position: 'start',
                    },
                ],
            },
        },
        point: {
            show: false,
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

    BC19.setupBBGraph({
        bindto: '#hospitalizations_icu_timeline_graph',
        size: {
            height: BC19.graphSizes.STANDARD,
        },
        data: {
            x: 'date',
            colors: BC19.colors,
            columns: [
                BC19.graphData.dates,
                BC19.graphData.hospitalizations.total,
                BC19.graphData.hospitalizations.icu,
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
                max: BC19.maxValues.hospitalizations,
                tick: {
                    stepSize: BC19.stepSizes.HOSPITALIZATIONS,
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
                BC19.graphData.dates,
                BC19.graphData.hospitalizations.residents,
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
                max: BC19.maxValues.hospitalizations,
                tick: {
                    stepSize: BC19.stepSizes.HOSPITALIZATIONS,
                },
            },
        },
    });

    BC19.setupBBGraph({
        bindto: '#isolation_timeline_graph',
        size: {
            height: BC19.graphSizes.STANDARD,
        },
        data: {
            x: 'date',
            colors: BC19.colors,
            columns: [
                BC19.graphData.dates,
                BC19.graphData.cases.totalCases,
                BC19.graphData.isolation.current,
                BC19.graphData.isolation.released,
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
                tick: {
                    stepSize: BC19.stepSizes.ISOLATION,
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
                BC19.graphData.dates,
                BC19.graphData.snf.curPatientCases,
                BC19.graphData.snf.curStaffCases,
                /*
                BC19.graphData.snf.totalPatientDeaths,
                BC19.graphData.snf.totalStaffDeaths,
                */
            ],
            names: {
                current_patient_cases: 'Current Patient Cases',
                current_staff_cases: 'Current Staff Cases',
                total_patient_deaths: 'Total Patient Deaths',
                total_staff_deaths: 'Total Staff Deaths',
            },
            order: null,
            types: {
                current_patient_cases: 'bar',
                current_staff_cases: 'bar',
                total_patient_deaths: 'step',
                total_staff_deaths: 'step',
            },
            groups: [
                ['current_patient_cases', 'current_staff_cases'],
                //'total_patient_deaths', 'total_staff_deaths'],
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
                tick: {
                    stepSize: BC19.stepSizes.SNF,
                },
            },
        },
    });
};


BC19.setDateRange = function(fromDate, toDate) {
    const domain = [
        moment(fromDate).format('YYYY-MM-DD'),
        moment(toDate).add(8, 'hour').format('YYYY-MM-DD'),
    ];

    const newDateRange = {
        from: fromDate,
        to: toDate,
    };

    if (newDateRange === BC19.dateRange) {
        return;
    }

    BC19.dateRange = newDateRange;

    const dateRangeThreshold = 5;

    BC19.els.dateRangeFrom.value = domain[0];
    BC19.els.dateRangeFrom.max =
        moment(toDate)
        .subtract(dateRangeThreshold, 'days')
        .format('YYYY-MM-DD');

    BC19.els.dateRangeThrough.value = moment(toDate).format('YYYY-MM-DD');
    BC19.els.dateRangeThrough.min =
        moment(fromDate)
        .add(dateRangeThreshold, 'days')
        .format('YYYY-MM-DD');

    BC19.graphs.forEach(graph => {
        graph.axis.range({
            min: {
                x: domain[0],
            },
            max: {
                x: domain[1],
            },
        });

        /*
         * A simple flush() doesn't fix the grid lines, so reach into
         * the internals.
         */
        graph.internal.resizeFunction();
    });
};


BC19.setupElements = function() {
    function onDateRangeChanged() {
        BC19.setDateRange(
            moment(dateRangeFromEl.value, 'YYYY-MM-DD').toDate(),
            moment(dateRangeThroughEl.value, 'YYYY-MM-DD').toDate());
    }

    const dateSelectorEl = document.getElementById('date-selector');
    BC19.els.dateSelector = dateSelectorEl;
    dateSelectorEl.addEventListener(
        'change',
        () => _onDateSelectorChanged(dateSelectorEl.value));

    const fromDateValue = BC19.firstMDate.format('YYYY-MM-DD');
    const throughDateValue = BC19.lastMDate.format('YYYY-MM-DD');

    const dateRangeFromEl = document.getElementById('date-range-from');
    BC19.els.dateRangeFrom = dateRangeFromEl;
    dateRangeFromEl.value = fromDateValue;
    dateRangeFromEl.min = fromDateValue;
    dateRangeFromEl.max = throughDateValue;
    dateRangeFromEl.addEventListener('change', onDateRangeChanged);

    const dateRangeThroughEl = document.getElementById('date-range-through');
    BC19.els.dateRangeThrough = dateRangeThroughEl;
    dateRangeThroughEl.value = throughDateValue
    dateRangeThroughEl.min = fromDateValue;
    dateRangeThroughEl.max = throughDateValue;
    dateRangeThroughEl.addEventListener('change', onDateRangeChanged);

    const bcdDayText = BC19.getDayText(BC19.latestCasesRow.date);
    const stateDayText = BC19.getDayText(BC19.latestStateDataRow.date);

    document.querySelectorAll('.bc19-o-bcd-update-day').forEach(el => {
        el.innerText = bcdDayText;
    });

    document.querySelectorAll('.bc19-o-state-update-day').forEach(el => {
        el.innerText = stateDayText;
    });

    document.getElementById('page-spinner').remove();

    document.querySelector('.bc19-c-dashboard')
        .classList.remove('-is-loading');
}


BC19.init = function() {
    fetch(new Request('data/json/timeline.min.json?' + moment().format('x')))
        .then(response => {
            if (response && response.status === 200) {
                try {
                    return response.json();
                } catch (e) {
                }
            }

            throw new Error(
                "Oh no! The latest COVID-19 data couldn't be loaded! " +
                "Please report this :)");
        })
        .then(timeline => {
            BC19.processTimelineData(timeline);

            BC19.setupElements();
            BC19.setupCounters(timeline);
            BC19.setupByAgeGraph(timeline);
            BC19.setupByRegionGraph(timeline);
            BC19.setupByHospitalGraph(timeline);
            BC19.setupMainTimelineGraphs(timeline);
        })
        .catch(msg => {
            console.log(msg);
            alert(msg);
        });
};


function _onDateSelectorChanged(value) {
    const rangeEl = document.querySelector('.bc19-c-option-pane__date-range');

    if (value === 'custom') {
        rangeEl.classList.add('-is-shown');
        return;
    }

    let fromMDate = BC19.firstMDate;
    let toMDate = BC19.lastMDate;

    rangeEl.classList.remove('-is-shown');

    if (value === 'days-7') {
        fromMDate = moment().subtract(7, 'days');
    } else if (value === 'days-14') {
        fromMDate = moment().subtract(14, 'days');
    } else if (value === 'days-30') {
        fromMDate = moment().subtract(30, 'days');
    } else if (value === 'days-60') {
        fromMDate = moment().subtract(60, 'days');
    } else if (value === 'days-90') {
        fromMDate = moment().subtract(90, 'days');
    }

    BC19.setDateRange(moment.max(fromMDate, BC19.firstMDate).toDate(),
                      moment.max(toMDate, BC19.lastMDate).toDate());
}
