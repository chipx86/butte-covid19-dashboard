window.BC19 = {
    COUNTY_POPULATION: 217769,

    colors: {
        cases: '#4783EF',
        new_cases: '#E86050',
        new_deaths: '#981000',

        neg_results: '#A8D6F1',
        pos_results: '#D85040',
        new_tests: '#C7DAFA',
        test_results: '#3BA859',

        in_isolation: '#DD0000',
        released_from_isolation: '#3BA859',

        hospitalizations: '#C783EF',
        icu: '#87063B',

        chico: '#4783EF',
        oroville: '#E7463B',
        gridley: '#3BA859',
        other: '#F9BD34',

        age_0_17: '#4783EF',
        age_18_49: '#E7463B',
        age_50_64: '#3BA859',
        age_65_plus: '#F9BD34',
    },

    graphs: [],
    graphsData: {},
    graphZoomGroups: {},
    zoomingGraphs: {},
    commonTimelineOptions: {
        bar: {
            radius: {
                ratio: 0.3,
                max: 50,
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
        resize: {
            auto: true,
        },
        tooltip: {
            linked: true,
        },
    },
};


BC19.parseDate = function(dateStr) {
    return new Date(dateStr + 'T00:00:00-07:00');
};


BC19.formatDate = function(date) {
    return date.toLocaleDateString('en-US', {
        month: 'long',
        day: 'numeric',
        year: 'numeric',
    });
};


BC19.getLatestFromTimeline = function(timeline, checkKeyFunc) {
    const dates = timeline.dates;

    for (let i = dates.length - 1; i >= 0; i--) {
        const dateInfo = dates[i];

        if (checkKeyFunc(dateInfo)) {
            dateInfo.i = i;

            return dateInfo;
        }
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

    const graphCasesInChico = ['chico'];
    const graphCasesInGridley = ['gridley'];
    const graphCasesInOroville = ['oroville'];
    const graphCasesInOtherRegion = ['other'];

    const graphCasesByAge0_17 = ['age_0_17'];
    const graphCasesByAge18_49 = ['age_18_49'];
    const graphCasesByAge50_64 = ['age_50_64'];
    const graphCasesByAge65Plus = ['age_65_plus'];

    const graphInIsolation = ['in_isolation'];
    const graphReleasedFromIsolation = ['released_from_isolation'];

    const graphHospitalizations = ['hospitalizations'];
    const graphICU = ['icu'];

    const graphNotes = [];

    let maxNewCases = 0;
    let maxNewDeaths = 0;

    let latestCasesRow;
    let latestStateDataRow;
    let latestPerHospitalDataRow;

    for (let i = 0; i < rows.length; i++) {
        const row = rows[i];

        row.i = i;

        const confirmedCases = row.confirmed_cases;
        const deltaConfirmedCases = Math.max(confirmedCases.delta_total, 0);
        const viralTests = row.viral_tests;
        const viralTestResults = viralTests.results;
        const regions = row.regions;
        const ageRanges = row.age_ranges_in_years;
        const stateHospital = row.hospitalizations.state_data;

        graphDates.push(row.date);
        graphTotalCases.push(confirmedCases.total);
        graphNewCases.push(deltaConfirmedCases);
        graphNewDeaths.push(row.deaths.delta_total);

        graphTotalTests.push(viralTests.total);
        graphNewTests.push(viralTests.delta_total);
        graphTotalTestResults.push(viralTests.results);
        graphPositiveResults.push(deltaConfirmedCases);

        if (viralTestResults !== null && deltaConfirmedCases !== null) {
            graphNegativeResults.push(viralTestResults - deltaConfirmedCases);
        } else {
            graphNegativeResults.push(0);
        }

        graphCasesInChico.push(regions.chico.cases);
        graphCasesInOroville.push(regions.oroville.cases);
        graphCasesInGridley.push(regions.gridley.cases);
        graphCasesInOtherRegion.push(regions.other.cases);

        graphCasesByAge0_17.push(ageRanges['0-17'])
        graphCasesByAge18_49.push(ageRanges['18-49'])
        graphCasesByAge50_64.push(ageRanges['50-64'])
        graphCasesByAge65Plus.push(row.age_ranges_in_years['65_plus'])

        graphInIsolation.push(row.in_isolation.current || 0);
        graphReleasedFromIsolation.push(row.in_isolation.total_released || 0);

        graphHospitalizations.push(stateHospital.positive || 0);
        graphICU.push(stateHospital.icu_positive || 0);

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

        if (row.confirmed_cases.total !== null) {
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
        },
        regions: {
            chico: graphCasesInChico,
            oroville: graphCasesInOroville,
            gridley: graphCasesInGridley,
            other: graphCasesInOtherRegion,
        },
        ageRanges: {
            '0_17': graphCasesByAge0_17,
            '18_49': graphCasesByAge18_49,
            '50_64': graphCasesByAge50_64,
            '65_plus': graphCasesByAge65Plus,
        },
        isolation: {
            current: graphInIsolation,
            released: graphReleasedFromIsolation,
        },
        hospitalizations: {
            total: graphHospitalizations,
            icu: graphICU,
        },
    };

    BC19.maxNewCases = maxNewCases;
    BC19.maxNewDeaths = maxNewDeaths;
    BC19.maxTotalCases = latestCasesRow.confirmed_cases.total;
};


BC19.setupBBGraph = function(options) {
    options = Object.assign({}, BC19.commonTimelineOptions, options);
    const zoomGroup = options.zoomGroup;

    if (zoomGroup) {
        if (options.zoom === undefined) {
            options.zoom = {
                enabled: {
                    type: 'drag',
                },
            };
        }

        options.zoom.onzoom = function(domain) {
            if (BC19.zoomingGraphs[zoomGroup] === null) {
                BC19.zoomingGraphs[zoomGroup] = graph;

                if (BC19.zoomingGraphs[zoomGroup] === graph) {
                    BC19.graphZoomGroups[zoomGroup].forEach(_graph => {
                        if (_graph !== graph) {
                            _graph.zoom(domain);
                        }
                    });
                }

                BC19.zoomingGraphs[zoomGroup] = null;
            }
        };

        options.zoom.resetButton = {
            onclick: function() {
                BC19.graphZoomGroups[zoomGroup].forEach(_graph => {
                    _graph.unzoom();
                });
            },
        };
    }

    const graph = bb.generate(options);
    BC19.graphs.push(graph);

    if (zoomGroup) {
        if (BC19.graphZoomGroups[zoomGroup] === undefined) {
            BC19.graphZoomGroups[zoomGroup] = [graph];
        } else {
            BC19.graphZoomGroups[zoomGroup].push(graph);
        }

        BC19.zoomingGraphs[zoomGroup] = null;
    }

    const svgEl = graph.element.querySelector('svg');
    svgEl.style.width = '100%';

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
                .attr('for', 'by_age_graph_' + d.data_id)
                .text(d.label)
                .node());

            this.appendChild(d3.create('div')
                .attr('class', 'bc19-c-bar-graph__bar')
                .attr('id', 'by_age_graph_' + d.data_id)
                .style('width', x(d.value) + '%')
                .text(showPct ? Math.round((d.value / total) * 100) + '%'
                              : d.value)
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
            const relValue = relValues[i];
            const formatRelValue =
                options.formatRelValues
                ? options.formatRelValues[i]
                : (value, relValue) => Math.abs(value - relValue);

            relValueEl.innerText = formatRelValue(value, relValue);
            relValueEl.classList.remove('-is-up');
            relValueEl.classList.remove('-is-down');

            if (relValue > value) {
                relValueEl.classList.add('-is-down');
            } else if (relValue < value) {
                relValueEl.classList.add('-is-up');
            }
        }
    }
},


BC19.setupCounters = function(timeline) {
    const dates = timeline.dates;
    const casesRow = timeline.latestCasesRow;
    const hospitalsRow = timeline.latestStateDataRow;
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
            value: curCasesTotal,
            relativeValues: [
                dates[casesI - 1].confirmed_cases.total,
            ],
            formatValue: value => (value / totalTests * 100).toFixed(2) + '%',
            formatRelValues: [
                (value, relValue) => {
                    const valuePct = value / totalTests * 100;
                    const relValuePct =
                        relValue / dates[casesI - 1].viral_tests.total * 100;

                    return (valuePct - relValuePct).toFixed(2) + '%';
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
},


BC19.setupByAgeGraph = function(timeline) {
    const ageRanges = timeline.latestCasesRow.age_ranges_in_years;

    BC19.setupBarGraph(
        d3.select('#by_age_graph'),
        {
            pct: true,
        },
        [
            {
                data_id: '0_17',
                label: '0-17',
                value: ageRanges['0-17'],
            },
            {
                data_id: '18_49',
                label: '18-49',
                value: ageRanges['18-49'],
            },
            {
                data_id: '50_64',
                label: '50-64',
                value: ageRanges['50-64'],
            },
            {
                data_id: '65_plus',
                label: '65+',
                value: ageRanges['65_plus'],
            },
        ]);
};


BC19.setupByRegionGraph = function(timeline) {
    const regions = timeline.latestCasesRow.regions;

    BC19.setupBarGraph(
        d3.select('#by_region_graph'),
        {
            pct: true,
        },
        [
            {
                data_id: 'chico',
                label: 'Chico',
                value: regions.chico.cases,
            },
            {
                data_id: 'oroville',
                label: 'Oroville',
                value: regions.oroville.cases,
            },
            {
                data_id: 'gridley',
                label: 'Gridley',
                value: regions.gridley.cases,
            },
            {
                data_id: 'other',
                label: 'Other',
                value: regions.other.cases,
            },
        ]);
};


BC19.setupByHospitalGraph = function(timeline) {
    const dateInfo = BC19.latestPerHospitalDataRow;
    const hospitalData = dateInfo.hospitalizations.state_data;

    BC19.setupBarGraph(
        d3.select('#by_hospital_graph'),
        {},
        [
            {
                data_id: 'enloe',
                label: 'Enloe Hospital',
                value: hospitalData.enloe_hospital,
            },
            {
                data_id: 'oroville',
                label: 'Oroville Hospital',
                value: hospitalData.oroville_hospital,
            },
        ]);
};


BC19.setupMainTimelineGraphs = function(timeline) {
    const totalCaseStepCount = 5;
    const newCaseStepCount = 2;
    const deathsStepCount = 2;

    BC19.setupBBGraph({
        bindto: '#total_cases_graph',
        size: {
            height: 380,
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
            x: {
                type: 'timeseries',
                label: {
                    position: 'outer-left',
                },
                tick: {
                    fit: false,
                    autorotate: true,
                    format: '%B %d',
                },
            },
            y: {
                padding: 120,
                max: Math.ceil(BC19.maxTotalCases / totalCaseStepCount) *
                     totalCaseStepCount,
                tick: {
                    stepSize: totalCaseStepCount,
                },
            },
        },
        zoomGroup: 'cases',
    });

    BC19.setupBBGraph({
        bindto: '#new_cases_graph',
        size: {
            height: 200,
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
            x: {
                type: 'timeseries',
                label: {
                    position: 'outer-left',
                },
                tick: {
                    fit: false,
                    autorotate: true,
                    format: '%B %d',
                },
            },
            y: {
                max: Math.ceil(BC19.maxNewCases / newCaseStepCount) *
                     newCaseStepCount,
                padding: 0,
                tick: {
                    stepSize: newCaseStepCount,
                },
            },
        },
        zoomGroup: 'cases',
    });

    BC19.setupBBGraph({
        bindto: '#deaths_graph',
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
        size: {
            height: 120,
        },
        axis: {
            x: {
                type: 'timeseries',
                label: {
                    position: 'outer-left',
                },
                tick: {
                    fit: false,
                    autorotate: true,
                    format: '%B %d',
                },
            },
            y: {
                max: Math.ceil(BC19.maxNewDeaths / deathsStepCount) *
                     deathsStepCount,
                padding: 0,
                tick: {
                    stepSize: deathsStepCount,
                },
            },
        },
        zoomGroup: 'cases',
    });

    BC19.setupBBGraph({
        bindto: '#cases_in_test_results_graph',
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
            x: {
                type: 'timeseries',
                label: {
                    position: 'outer-left',
                },
                tick: {
                    fit: false,
                    autorotate: true,
                    format: '%B %d',
                },
            },
            y: {
                tick: {
                    stepSize: 25,
                },
            },
        },
        legend: {
            show: true,
        },
        zoomGroup: 'viral-tests',
    });

    BC19.setupBBGraph({
        bindto: '#test_results_graph',
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
                total_tests: 'area-step',
                test_results: 'bar',
                new_tests: 'bar',
            },
        },
        axis: {
            x: {
                type: 'timeseries',
                label: {
                    position: 'outer-left',
                },
                tick: {
                    fit: false,
                    autorotate: true,
                    format: '%B %d',
                },
            },
            y: {
                tick: {
                    stepSize: 100,
                },
            },
        },
        legend: {
            show: true,
        },
        zoomGroup: 'viral-tests',
    });
};


BC19.showMoreGraphs = function() {
    const commonOptions = {
        legend: {
            show: true,
        },
        size: {
            height: 300,
        },
        axis: {
            x: {
                type: 'timeseries',
                tick: {
                    fit: false,
                    format: '%B %d',
                },
            },
        },
        zoom: {
            enabled: {
                type: 'drag',
            },
        },
    };

    const sectionEl = document.getElementById('more-graphs-section');
    sectionEl.classList.add('-is-open');

    BC19.setupBBGraph(Object.assign({}, commonOptions, {
        bindto: '#cases_by_region_timeline_graph',
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
            y: {
                tick: {
                    stepSize: 10,
                },
            },
            x: commonOptions.axis.x,
        },
    }));

    BC19.setupBBGraph(Object.assign({}, commonOptions, {
        bindto: '#cases_by_age_timeline_graph',
        data: {
            x: 'date',
            colors: BC19.colors,
            columns: [
                BC19.graphData.dates,
                BC19.graphData.ageRanges['0_17'],
                BC19.graphData.ageRanges['18_49'],
                BC19.graphData.ageRanges['50_64'],
                BC19.graphData.ageRanges['65_plus'],
            ],
            names: {
                age_0_17: '0-17 Years',
                age_18_49: '18-49 Years',
                age_50_64: '50-64 Years',
                age_65_plus: '65+ Years',
            },
            order: null,
            types: {
                age_0_17: 'bar',
                age_18_49: 'bar',
                age_50_64: 'bar',
                age_65_plus: 'bar',
            },
            groups: [
                ['age_0_17', 'age_18_49', 'age_50_64', 'age_65_plus'],
            ],
        },
        axis: {
            y: {
                tick: {
                    stepSize: 10,
                },
            },
            x: commonOptions.axis.x,
        },
    }));

    BC19.setupBBGraph(Object.assign({}, commonOptions, {
        bindto: '#isolation_timeline_graph',
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
        axis: {
            y: {
                tick: {
                    stepSize: 10,
                },
            },
            x: commonOptions.axis.x,
        },
    }));

    BC19.setupBBGraph(Object.assign({}, commonOptions, {
        bindto: '#hospitalizations_icu_timeline_graph',
        data: {
            x: 'date',
            colors: BC19.colors,
            columns: [
                BC19.graphData.dates,
                BC19.graphData.hospitalizations.total,
                BC19.graphData.hospitalizations.icu,
            ],
            names: {
                cases: 'Confirmed Cases',
                hospitalizations: 'Currently In Isolation',
                icu: 'Total Released From Isolation',
            },
            order: null,
            types: {
                cases: 'area-step',
                hospitalizations: 'area-step',
                icu: 'area-step',
            },
        },
    }));
};


BC19.setupGraphs = function(buildTimeStamp) {
    fetch(new Request('data/json/timeline.json?' + buildTimeStamp))
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

            timeline.latestCasesRow = BC19.latestCasesRow;
            timeline.latestStateDataRow = BC19.latestStateDataRow;

            document.getElementById('case_updated_date').innerText =
                BC19.formatDate(BC19.parseDate(BC19.latestCasesRow.date));

            document.getElementById('hospital_updated_date').innerText =
                BC19.formatDate(BC19.parseDate(BC19.latestStateDataRow.date));

            BC19.setupCounters(timeline);
            BC19.setupByAgeGraph(timeline);
            BC19.setupByRegionGraph(timeline);
            BC19.setupByHospitalGraph(timeline);
            BC19.setupMainTimelineGraphs(timeline);

            document.getElementById('more-graphs-expander').addEventListener(
                'click',
                event => BC19.showMoreGraphs());

            if (window.location.hash === '#all-charts') {
                BC19.showMoreGraphs();
            }
        })
        /*
        .catch(msg => {
            alert(msg);
        });
        */
};
