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

    els: {
    },

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
        resize: {
            auto: false,
        },
        tooltip: {
            linked: true,
        },
        padding: {
            right: 10,
        },
    },
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
    BC19.firstMDate = BC19.parseMDate(timeline.dates[0].date);
    BC19.lastMDate = BC19.parseMDate(timeline.dates[rows.length - 1].date);
    BC19.timeline = timeline;

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
            value: curCasesTotal / totalTests * 100,
            relativeValues: [
                dates[casesI - 1].confirmed_cases.total /
                dates[casesI - 1].viral_tests.total * 100,
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
    const ageRanges = BC19.latestCasesRow.age_ranges_in_years;
    const prevIndex = BC19.latestCasesRow.i - 1;
    const prevAgeRanges = timeline.dates[prevIndex].age_ranges_in_years;

    BC19.setupBarGraph(
        d3.select('#by_age_graph'),
        {},
        [
            {
                data_id: '0_17',
                label: '0-17',
                value: ageRanges['0-17'],
                relValue: ageRanges['0-17'] - prevAgeRanges['0-17'],
            },
            {
                data_id: '18_49',
                label: '18-49',
                value: ageRanges['18-49'],
                relValue: ageRanges['18-49'] - prevAgeRanges['18-49'],
            },
            {
                data_id: '50_64',
                label: '50-64',
                value: ageRanges['50-64'],
                relValue: ageRanges['50-64'] - prevAgeRanges['50-64'],
            },
            {
                data_id: '65_plus',
                label: '65+',
                value: ageRanges['65_plus'],
                relValue: ageRanges['65_plus'] - prevAgeRanges['65_plus'],
            },
        ]);
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
                localtime: false,
                label: {
                    position: 'outer-left',
                },
                tick: {
                    fit: false,
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
                localtime: false,
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
                localtime: false,
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
                localtime: false,
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
                localtime: false,
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
                localtime: false,
                tick: {
                    fit: false,
                    format: '%B %d',
                },
            },
        },
    };

    const sectionEl = document.getElementById('more-graphs-section');
    sectionEl.classList.add('-is-open');

    document.getElementById('more-graphs-expander').remove();

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
    }));
};


BC19.setDateRange = function(fromDate, toDate, fromResize) {
    const domain = [fromDate, moment(toDate).add(8, 'hour').toDate()];

    const newDateRange = {
        from: fromDate,
        to: toDate,
    };

    if (newDateRange === BC19.dateRange && !fromResize) {
        return;
    }

    BC19.dateRange = newDateRange;

    const dateRangeThreshold = 5;

    BC19.els.dateRangeFrom.value = moment(fromDate).format('YYYY-MM-DD');
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
        if (fromResize) {
            graph.flush(false, true);
        }

        /*
         * Ideally we wouldn't reach into the internals of billboard.js, but
         * the standard zoom support can't be manually-driven. It's always
         * interactive once enabled, and that doesn't work for us. So we
         * perform the same internal state updates it would.
         */
        graph.internal.initZoom();
        graph.internal.x.domain(domain);
        graph.internal.zoomScale = graph.internal.x;
        graph.internal.xAxis.scale(graph.internal.zoomScale);

        graph.internal.redraw({
            withTransition: true,
            withY: false,
            withDimension: false,
        });
    });
};


BC19.setupElements = function() {
    function onDateRangeChanged() {
        BC19.setDateRange(
            moment(dateRangeFromEl.value, 'YYYY-MM-DD').toDate(),
            moment(dateRangeThroughEl.value, 'YYYY-MM-DD').toDate());
    }

    document.getElementById('more-graphs-expander').addEventListener(
        'click',
        () => BC19.showMoreGraphs());

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


    document.getElementById('case_updated_date').innerText =
        BC19.formatMDate(BC19.parseMDate(BC19.latestCasesRow.date));

    document.getElementById('hospital_updated_date').innerText =
        BC19.formatMDate(BC19.parseMDate(BC19.latestStateDataRow.date));

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

    window.addEventListener('resize', () => _onWindowResize());
}


BC19.init = function() {
    fetch(new Request('data/json/timeline.json'))
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

            if (window.location.hash === '#all-charts') {
                BC19.showMoreGraphs();
            }
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


function _onWindowResize() {
    if (BC19.dateRange) {
        BC19.setDateRange(BC19.dateRange.from,
                          BC19.dateRange.to,
                          true);
    } else {
        BC19.forEachGraphAsync(graph => graph.flush(false, true));
    }
}
