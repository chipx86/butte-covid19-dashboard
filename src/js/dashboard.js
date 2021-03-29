window.BC19 = {
    COUNTY_POPULATION: 217769,

    tickCounts: {
        VERY_TALL: 15,
        STANDARD: 10,
        MEDIUM: 9,
        SMALL: 5,
        VERY_SMALL: 5,
    },

    graphSizes: {
        VERY_TALL: 380,
        STANDARD: 240,
        MEDIUM: 200,
        SMALL: 120,
        VERY_SMALL: 120,
    },

    colors: {
        cases: '#57A3FF',
        new_cases: '#E86050',

        total_deaths: '#A81010',
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

        chico: '#3773DF',
        oroville: '#F7767B',
        gridley: '#6BD079',
        biggs_gridley: '#6BD079',
        other: '#F9BD34',

        age_0_17: '#3773DF',
        age_18_49: '#F7767B',
        age_50_64: '#6BD079',
        age_65_plus: '#F9BD34',

        current_patient_cases: '#D0A9D9',
        current_staff_cases: '#8FC3E7',
        new_patient_deaths: '#981000',
        new_staff_deaths: '#F88000',

        jail_inmate_cur_cases: '#333333',
        jail_inmate_pop: '#999999',
        jail_staff_total_cases: '#2222FF',
    },

    els: {},
    graphs: [],

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

    /* Data loaded in from the dashboard JSON file. */
    barGraphsData: null,
    firstMDate: null,
    graphData: null,
    lastMDate: null,
    latestRowDates: null,
    latestRowIndexes: null,
    maxValues: null,
    monitoringTier: null,
    reportTimestamp: null,
};


/**
 * Parse a "YYYY-MM-DD" date string into a moment object.
 *
 * This assumes that the date will always be in PST (specifically, -0700).
 *
 * Args:
 *     dateStr (string):
 *         The date string to parse.
 *
 * Returns:
 *     moment:
 *     The moment-wrapped date.
 */
BC19.parseMDate = function(dateStr, fmt='YYYY-MM-DD Z') {
    return moment.tz(dateStr, fmt, 'US/Pacific');
};


/**
 * Return a relative date representation.
 *
 * If the date is today or yesterday (based on the current date), this will
 * return a relative date ("today" or "yesterday"). Otherwise, it will
 * return a day of the week.
 *
 * Args:
 *     date (Date):
 *         The date to format.
 *
 * Returns:
 *     string:
 *     "today" or "yesterday", if appropriate for the date. Otherwise, a day
 *     of the week.
 */
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


/**
 * Process the downloaded dashboard data.
 *
 * This is the main function used by the website to load data for display.
 * It parses the ``bc19-dashboard.*.min.json`` data feed, loading the
 * information for the graphs and counters on the page, as well as the
 * variables in the :js:data:`BC19` namespace at the top of this file.
 *
 * Args:
 *     data (object):
 *         The deserialized dashboard data.
 */
BC19.processDashboardData = function(data) {
    BC19.firstMDate = BC19.parseMDate(data.dates.first);
    BC19.lastMDate = BC19.parseMDate(data.dates.last);
    BC19.reportTimestamp = BC19.parseMDate(data.reportTimestamp,
                                           'YYYY-MM-DD hh:mm:ss Z')

    BC19.latestRowIndexes = data.latestRows;
    BC19.latestRowDates = Object.fromEntries(
        Object.entries(data.dates.rows).map(
            pair => [pair[0], BC19.parseMDate(pair[1])]));

    BC19.barGraphsData = data.barGraphs;
    BC19.countersData = data.counters;
    BC19.graphData = data.timelineGraphs;
    BC19.maxValues = data.maxValues;
    BC19.monitoringTier = data.monitoringTier;

    BC19.defaultTimelineDomain = [
        moment(BC19.lastMDate).subtract(120, 'days').format('YYYY-MM-DD'),
        moment(BC19.lastMDate).add(1, 'days').format('YYYY-MM-DD'),
    ];
};


/**
 * Return the desired graph axis tick step size, based on a value.
 *
 * This attempts to calculate the number of values represented in-between
 * each tick in a graph, based on the number of ticks that will be displayed
 * and the maximum value for the graph.
 *
 * It starts by computing a "nearest" step size (5, 10, 25, 50, 100, or 1000,
 * depending on the maximum value), and then computing a step size from that.
 *
 * The resulting step size will always ensure that the maximum value shown in
 * the graph will never be greater than the highest tick.
 *
 * Args:
 *     maxValue (number):
 *         The maximum value being shown in the graph.
 *
 *     numTicks (number):
 *         The number of ticks that will be shown on the graph.
 *
 * Returns:
 *     number:
 *     The step size between ticks.
 */
BC19.getStepSize = function(maxValue, numTicks) {
    let nearest = 2;

    if (maxValue > 10000) {
        nearest = 1000;
    } else if (maxValue > 1000) {
        nearest = 100;
    } else if (maxValue > 500) {
        nearest = 50;
    } else if (maxValue > 100) {
        nearest = 25;
    } else if (maxValue > 50) {
        nearest = 10;
    } else if (maxValue > 20) {
        nearest = 5;
    }

    return Math.ceil((maxValue / numTicks + 1) / nearest) * nearest;
};


/**
 * Return the maximum Y axis value on a graph.
 *
 * This will compute the maximum Y value based on the maximum value that will
 * be displayed in the graph and the number of ticks to display. The result
 * will always be at least as large as the maximum value.
 *
 * This is used to set the appropriate display range for a graph.
 *
 * Args:
 *     maxValue (number):
 *         The maximum value being shown in the graph.
 *
 *     numTicks (number):
 *         The number of ticks that will be shown on the graph.
 *
 * Returns:
 *     number:
 *     The maximum Y value for the graph.
 */
BC19.getMaxY = function(maxValue, numTicks) {
    const stepSize = BC19.getStepSize(maxValue, numTicks);

    return Math.ceil((maxValue / stepSize)) * stepSize;
};


/**
 * Set up a billboard.js-backed graph.
 *
 * This will create and render the graph based on a combination of the
 * provided options and the standard timeline options
 * (:js:data:`BC19.commonTimelineOptions`) and store the graph in
 * :js:data:`BC19.graphs`.
 *
 * Args:
 *     options (object):
 *         The options for the graph. These are options that are accepted
 *         by :js:func:`bb.generate`.
 *
 * Returns:
 *     object:
 *     The graph object.
 */
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


/**
 * Set up a bar graph.
 *
 * This will create and render a bar graph based on the provided options
 * and data.
 *
 * These are used for the demographics and hospitalization information on
 * the side of the page (in desktop mode).
 *
 * Args:
 *     graph (object):
 *         The D3-wrapped graph element.
 *
 *     options (object):
 *         Options for the graph.
 *
 *     data (Array of object):
 *         Data for the bar graph. Each item is an object with the following:
 *
 *         ``data_id`` (string):
 *             An ID uniquely representing the bar.
 *
 *         ``label`` (string):
 *             The visible label for the bar.
 *
 *         ``value`` (number):
 *             The value associated with the bar.
 *
 *         ``relValue`` (number):
 *             The previous value that ``value`` is relative to (used to show
 *             a delta indicator).
 *
 * Option Args:
 *     formatValue (function, optional):
 *         A function to format the value for display. Defaults to showing
 *         the value in the current locale.
 *
 *     pct (boolean, optional):
 *         Whether to show a percentage beside the bar.
 *
 *     skipIfZero (boolean, optional):
 *         Skip the bar if the value is 0.
 */
BC19.setupBarGraph = function(graph, options={}, data) {
    const showPct = !!options.pct;
    const formatValue = options.formatValue || function(value) {
        return value.toLocaleString();
    };

    if (options.skipIfZero) {
        data = data.filter(item => (item.value > 0));
    }

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

            const valueText = formatValue(d.value);

            this.appendChild(d3.create('div')
                .attr('class', 'bc19-c-bar-graph__bar')
                .attr('id', 'bar_graph_' + d.data_id)
                .style('width', x(d.value) + '%')
                .text(valueText)
                .node());

            if (showPct) {
                this.appendChild(d3.create('div')
                    .attr('class', 'bc19-c-bar-graph__pct')
                    .attr('id', 'bar_graph_' + d.data_id)
                    .text(Math.round((d.value / total) * 100) + '%')
                    .node());
            }

            let relValue = '';
            let relClass = '';
            let relTitle;

            if (d.relValue > 0) {
                relValue = formatValue(d.relValue);
                relClass = '-is-up';
                relTitle = '+' + relValue + ' since yesterday';
            } else if (d.relValue < 0) {
                relValue = formatValue(-d.relValue);
                relClass = '-is-down';
                relTitle = '-' + relValue + ' since yesterday';
            }

            if (relValue !== '') {
                this.appendChild(d3.create('span')
                    .attr('class', 'bc19-c-bar-graph__rel-value ' + relClass)
                    .attr('title', relTitle)
                    .text(relValue)
                    .node());
            }
        });
};


/**
 * Set the value for a counter.
 *
 * Args:
 *     elID (string):
 *         The ID of the element for the counter component.
 *
 *     options (object):
 *         Options for the counter's display.
 *
 * Option Args:
 *     formatRelValues (Array of function, optional):
 *         An array of functions to format relative values for display. Each
 *         will take two aprameters, the value and the relative value, and must
 *         return a string.
 *
 *         This must be the same length as the number of relative value
 *         elements.
 *
 *         If not provided, it will default to showing the difference between
 *         values.
 *
 *     formatValue (function, optional):
 *         A function to format the value for display. Defaults to showing
 *         the value in the current locale.
 *
 *     relativeValues (Array of number):
 *         An array of previous value that ``value`` is relative to.
 *
 *         This must be the same length as the number of relative value
 *         elements.
 *
 *     value (number):
 *         The value to show in the main counter.
 */
BC19.setCounter = function(elID, options) {
    const el = document.getElementById(elID);
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

            if (relValue === null || isNaN(relValue)) {
                relValueEl.innerText = 'no data';
                continue;
            }

            const formatRelValue =
                options.formatRelValues
                ? options.formatRelValues[i]
                : (value, relValue) => {
                    return Math.abs(value - relValue).toLocaleString()
                };

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


/**
 * Set up all the counters on the page.
 */
BC19.setupCounters = function() {
    const data = BC19.countersData;

    BC19.setCounter('total-cases-counter', data.totalCases);
    BC19.setCounter('deaths-counter', data.totalDeaths);
    BC19.setCounter('in-isolation-counter', data.inIsolation);
    BC19.setCounter('hospitalized-residents-counter',
                    data.hospitalizedResidents);
    BC19.setCounter('hospitalized-counter', data.allHospitalized);
    BC19.setCounter('icu-counter', data.inICU);
    BC19.setCounter('vaccines-allocated-counter', data.vaccinesAllocated);
    BC19.setCounter('vaccines-administered-counter',
                    data.vaccinesAdministered);
    BC19.setCounter('vaccines-ordered1-counter', data.vaccinesOrdered1);
    BC19.setCounter('vaccines-ordered2-counter', data.vaccinesOrdered2);
    BC19.setCounter('vaccines-received-counter', data.vaccinesReceived);
    BC19.setCounter('total-tests-counter', data.totalTests);
    BC19.setCounter('positive-test-results-counter', data.positiveTestResults);
    BC19.setCounter('positive-test-rate-counter',
        {
            value: data.positiveTestRate.value,
            relativeValues: data.positiveTestRate.relativeValues,
            formatValue: value => value.toFixed(2) + '%',
            formatRelValues: [
                (value, relValue) => {
                    return Math.abs(value - relValue).toFixed(2) + '%';
                },
            ],
        });
    BC19.setCounter('jail-inmate-pop-counter', data.jailInmatePop);
    BC19.setCounter('jail-inmate-total-tests', data.jailInmateTotalTests);
    BC19.setCounter('jail-inmate-cur-cases', data.jailInmateCurCases);
    BC19.setCounter('jail-inmate-pos-rate',
        {
            value: data.jailInmatePosRate.value,
            relativeValues: data.jailInmatePosRate.relativeValues,
            formatValue: value => value.toFixed(2) + '%',
            formatRelValues: [
                (value, relValue) => {
                    return Math.abs(value - relValue).toFixed(2) + '%';
                },
            ],
        });
    BC19.setCounter('jail-staff-total-tests', data.jailStaffTotalTests);
    BC19.setCounter('jail-staff-total-cases', data.jailStaffTotalCases);
};


/**
 * Set up the bar graphs.
 */
BC19.setupBarGraphs = function() {
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
BC19.setupTimelineGraphs = function() {
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
            columns: [
                graphData.dates,
                graphData.cases.totalCases,
            ],
            names: {
                cases: 'Total Cases',
            },
            types: {
                cases: 'bar',
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
                max: BC19.getMaxY(Math.max(per1KPopRound + 20,
                                           maxValues.oneWeekCaseRate),
                                  tickCounts.STANDARD),
                padding: 0,
                tick: {
                    stepSize: BC19.getStepSize(maxValues.oneWeekCaseRate,
                                               tickCounts.STANDARD),
                },
            },
        },
        point: {
            show: false,
        },
        tooltip: {
            linked: true,

            format: {
                value: (value, ratio, id) => {
                    const per1K = Math.round(value / per1KPop * 100);
                    return `${value} (~${per1K} per 100K people)`;
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
                total_deaths: 'bar',
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
        bindto: '#cases_by_age_timeline_graph',
        size: {
            height: BC19.graphSizes.STANDARD,
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
            types: {
                age_0_4: 'bar',
                age_5_12: 'bar',
                age_13_17: 'bar',
                age_18_24: 'bar',
                age_25_34: 'bar',
                age_35_44: 'bar',
                age_45_54: 'bar',
                age_55_64: 'bar',
                age_65_74: 'bar',
                age_75_plus: 'bar',

                age_0_17: 'bar',
                age_18_49: 'bar',
                age_50_64: 'bar',
                age_65_plus: 'bar',
            },
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
                max: BC19.getMaxY(maxValues.totalCases, tickCounts.STANDARD),
                padding: 0,
                tick: {
                    stepSize: BC19.getStepSize(maxValues.totalCases,
                                               tickCounts.STANDARD),
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
            type: 'bar',
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
                max: BC19.getMaxY(maxValues.totalCases, tickCounts.STANDARD),
                padding: 0,
                tick: {
                    stepSize: BC19.getStepSize(maxValues.totalCases,
                                               tickCounts.STANDARD),
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
                new_tests: 'bar',
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

    const vaccineDosesDataMap = {};
    vaccineDosesDataMap[graphData.vaccines.firstDosesPct[0]] =
        graphData.vaccines.firstDoses;
    vaccineDosesDataMap[graphData.vaccines.fullDosesPct[0]] =
        graphData.vaccines.fullDoses;

    const vaccineDosesGraph = BC19.setupBBGraph({
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
            type: 'step',
            names: {
                vaccines_1st_dose_pct: '1 or more doses',
                vaccines_full_doses_pct: 'Fully vaccinated',
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
        point: {
            show: false,
        },
        tooltip: {
            format: {
                value: (value, ratio, id, index) => {
                    const fmtValue = `${value.toFixed(2)}%`;

                    if (index > 0) {
                        const prevValue =
                            vaccineDosesGraph.data(id)[0]
                            .values[index - 1].value;
                        const fmtRelValue =
                            Math.abs(value - prevValue).toFixed(2) + '%';
                        const relStr = (prevValue > value
                                        ? `-${fmtRelValue}`
                                        : `+${fmtRelValue}`);
                        const numPeople = vaccineDosesDataMap[id][index + 1];
                        const prevNumPeople = vaccineDosesDataMap[id][index];

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
        point: {
            show: false,
        },
        tooltip: {
            format: {
                value: (value, ratio, id, index) => {
                    const fmtValue = `${value.toFixed(2)}%`;

                    if (index > 0) {
                        const prevValue =
                            vaccineDosesByTypeGraph.data(id)[0]
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
            types: {
                current_patient_cases: 'bar',
                current_staff_cases: 'bar',
                total_patient_deaths: 'step',
                total_staff_deaths: 'step',
            },
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
            types: {
                current_patient_cases: 'bar',
                current_staff_cases: 'bar',
                total_patient_deaths: 'step',
                total_staff_deaths: 'step',
            },
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
                max: BC19.getMaxY(maxValues.adultSeniorCare, tickCounts.MEDIUM),
                padding: 0,
                tick: {
                    stepSize: BC19.getStepSize(maxValues.adultSeniorCare,
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
 * Set the date range for all the timeline graphs.
 *
 * This will update the selector at the bottom of the page and redraw all
 * graphs to center on the new range.
 *
 * Args:
 *     fromDate (Date):
 *         The beginning date for the range.
 *
 *     toDate (Date):
 *         The ending date for the range.
 */
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
    /* Show the report timestamp. */
    const timestampEl = document.getElementById('report-timestamp');
    timestampEl.innerText = BC19.reportTimestamp.format(
        'dddd, MMMM Do, YYYY @ h:mm a');

    /* Show the current monitoring tier. */
    const tier = BC19.monitoringTier;

    const tierSectionEl = document.getElementById('monitoring-tier-section');
    tierSectionEl.classList.add(`-is-tier-${tier.toLowerCase()}`);

    const tierEl = document.getElementById('monitoring-tier');
    tierEl.innerText = tier;

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


    /* Update the dates in the counters. */
    const datesMap = {};

    document.querySelectorAll('.bc19-o-update-day').forEach(el => {
        const key = el.dataset.key;

        if (!datesMap.hasOwnProperty(key)) {
            datesMap[key] = BC19.getDayText(BC19.latestRowDates[key]);
        }

        el.innerText = datesMap[key];
    });

    document.getElementById('page-spinner').remove();

    const dashboardEl = document.querySelector('.bc19-c-dashboard');
    dashboardEl.classList.remove('-is-loading');

    const noticeEl = document.querySelector('.bc19-c-dashboard__notice');

    if (noticeEl) {
        function _updateSizeForNotice() {
            const rect = noticeEl.getBoundingClientRect();

            dashboardEl.style.marginTop = `${rect.height}px`;
        }

        window.addEventListener('resize', _updateSizeForNotice);
        _updateSizeForNotice();
    }
}


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
    fetch(new Request('data/json/bc19-dashboard.1.min.json?' +
                      moment().format('x')))
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
        .then(dashboardData => {
            BC19.processDashboardData(dashboardData);

            BC19.setupElements();
            BC19.setupCounters();
            BC19.setupBarGraphs();
            BC19.setupTimelineGraphs();
        })
        .catch(msg => {
            console.error(msg);
            alert(msg);
        });
};


/**
 * Handle changes to the date selector.
 *
 * If the user has chosen "Custom", date range fields will be shown.
 *
 * Any other selection will result in a date range being calculated. The
 * graphs will then be updated to show this range.
 *
 * Args:
 *     value (string):
 *         The value chosen in the dropdown.
 */
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
    } else if (value === 'days-120') {
        fromMDate = moment().subtract(120, 'days');
    } else if (value === 'days-180') {
        fromMDate = moment().subtract(180, 'days');
    } else if (value === 'days-365') {
        fromMDate = moment().subtract(365, 'days');
    }

    BC19.setDateRange(moment.max(fromMDate, BC19.firstMDate).toDate(),
                      moment.max(toMDate, BC19.lastMDate).toDate());
}
