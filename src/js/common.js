window.BC19 = {
    COUNTY_POPULATION: 217769,

    tickCounts: {
        VERY_TALL: 15,
        STANDARD: 10,
        MEDIUM: 10,
        SMALL: 5,
        VERY_SMALL: 5,
    },

    graphSizes: {
        VERY_TALL: 380,
        STANDARD: 250,
        MEDIUM: 250,
        SMALL: 160,
        VERY_SMALL: 100,
    },

    colors: {
        cases: '#57A3FF',
        new_cases: '#E86050',

        total_deaths: '#A81010',
        new_deaths: '#981000',

        neg_results: '#E0EDFD',
        pos_results: '#D85040',
        new_tests: '#C7CA9A',
        test_results: '#57A3FF',
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
        grid: {
            y: {
                show: true,
            },
        },
        interaction: {
            inputType: {
                touch: false,
            },
        },
        legend: {
            show: false,
        },
        line: {
            step: {
                type: 'step',
            },
        },
        tooltip: {
            linked: true,
        },
        padding: {
            right: 10,
        },
        point: {
            focus: {
                only: true,
            },
        },
        svg: {
            classname: 'bb-graph-svg',
        },
        transition: {
            duration: 0,
        },
    },

    defaultTimelineDomain: null,

    /* Data loaded in from the dashboard JSON file. */
    barGraphsData: null,
    firstMDate: null,
    graphData: null,
    scheduledGraphData: [],
    delayedScheduledGraphData: [],
    scheduledGraphRangeUpdates: [],
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
 * Return a relative date representation using days.
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
 * Return a relative date representation using weeks.
 *
 * If the date is this week or last week week (based on the current date),
 * this will return a relative date ("this week" or "last week"). Otherwise,
 * it will return a number of weeks ago.
 *
 * Args:
 *     date (Date):
 *         The date to format.
 *
 * Returns:
 *     string:
 *     "this week" or "last week", if appropriate for the date. Otherwise, a
 *     number of weeks ago.
 */
BC19.getWeeksText = function(date) {
    const weeks = moment().diff(date, 'weeks');

    if (weeks === 0) {
        return 'this week';
    } else if (weeks === 1) {
        return 'last week';
    } else {
        return `${weeks} weeks ago`;
    }
};


/**
 * Format a number as a percentage.
 *
 * Args:
 *     value (number):
 *         The number to format.
 *
 * Returns:
 *     string:
 *     The formatted percentage.
 */
BC19.formatPct = function(value) {
    return value.toFixed(2) + '%';
};


/**
 * Format relative values as a percentage.
 *
 * Args:
 *     value (number):
 *         One number to include in the relative calculation.
 *
 *     relValue (number):
 *         The other number to include in the relative calculation.
 *
 * Returns:
 *     string:
 *     The formatted percentage.
 */
BC19.formatPctRel = function(value, relValue) {
    return BC19.formatPct(Math.abs(value - relValue));
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

    const range = BC19.getTimelineDateRange();
    BC19.defaultTimelineDomain = [
        range[0].format('YYYY-MM-DD'),
        range[1].format('YYYY-MM-DD'),
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

    if (maxValue > 50000) {
        nearest = 20000;
    } else if (maxValue > 10000) {
        nearest = 2000;
    } else if (maxValue > 5000) {
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
    } else {
        nearest = 2;
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

    return Math.max(Math.ceil((maxValue / stepSize)) * stepSize, 10);
};


/**
 * Return a new billboard.js graph element for the DOM.
 *
 * Args:
 *     options (object):
 *         Options for the element.
 *
 * Option Args:
 *     dataID (string):
 *         The ID of the data, used to build DOM IDs for the element.
 *
 *     subtitles (Array of string, optional):
 *         Subtitles to include below the main title.
 *
 *     title (string, optional):
 *         The title to show above the element.
 *
 * Returns:
 *     HTMLElement:
 *     The new element.
 */
BC19.makeBBGraphElement = function(options) {
    const dataID = options.dataID;
    const labelID = `${dataID}_label`;

    const subtitles = options.subtitles || [];

    const el = document.createElement('figure');
    el.classList.add('bc19-c-timeline-graph');

    if (options.title) {
        const titleEl = document.createElement('h3');
        titleEl.classList.add('bc19-c-timeline-graph__title');
        titleEl.id = labelID;
        titleEl.innerText = options.title;
        el.appendChild(titleEl);
    }

    subtitles.forEach(subtitle => {
        const subtitleEl = document.createElement('h4');
        subtitleEl.classList.add('bc19-c-timeline-graph__subtitle');
        subtitleEl.innerText = subtitle;
        el.appendChild(subtitleEl);
    });

    const dataEl = document.createElement('div');
    dataEl.id = dataID;
    dataEl.setAttribute('aria-labelled-by', labelID);
    el.appendChild(dataEl);

    return el;
};


/**
 * Return a new section header element.
 *
 * Args:
 *     options (object):
 *         Options for the element.
 *
 * Option Args:
 *     ariaLabel (string, optional):
 *         The ARIA label assigned to the element.
 *
 *     id (string, optional):
 *         The ID of the element.
 *
 *     title (string):
 *         The title to show in the header.
 *
 * Returns:
 *     HTMLElement:
 *     The new element.
 */
BC19.makeSectionHeaderElement = function(options) {
    const headerEl = document.createElement('header');
    headerEl.classList.add('bc19-c-dashboard__header');

    if (options.id) {
        headerEl.id = options.id;
    }

    if (options.ariaLabel) {
        headerEl.setAttribute('aria-label', options.ariaLabel);
    }

    const titleEl = document.createElement('h2');
    titleEl.innerText = options.title;
    headerEl.appendChild(titleEl);

    return headerEl;
};


/**
 * Return a new sources element.
 *
 * Args:
 *     sources (Array of object):
 *         The list of sources, each an object with ``url`` and optional
 *         ``label`` attributes.
 *
 * Returns:
 *     HTMLElement:
 *     The new element.
 */
BC19.makeSourcesElement = function(sources) {
    const sourcesEl = document.createElement('p');
    sourcesEl.classList.add('bc19-c-dashboard__sources');

    if (sources.length === 1 && !sources[0].label) {
        const linkEl = document.createElement('a');
        linkEl.setAttribute('href', sources[0].url);
        linkEl.innerText = 'Source';
        sourcesEl.appendChild(linkEl);
    } else {
        const labelEl = document.createElement('strong');

        if (sources.length === 1) {
            labelEl.innerText = 'Source: ';
        } else {
            labelEl.innerText = 'Sources: ';
        }

        sourcesEl.appendChild(labelEl);

        for (let i = 0; i < sources.length; i++) {
            const sourceInfo = sources[i];

            const linkEl = document.createElement('a');
            linkEl.setAttribute('href', sourceInfo.url);
            linkEl.innerText = sourceInfo.label;
            sourcesEl.appendChild(linkEl);

            if (i < sourceInfo.length - 1) {
                sourcesEl.appendChild(document.createTextNode(', '));
            }
        }
    }

    return sourcesEl;
};


/**
 * Return a new section element.
 *
 * Args:
 *     options (object):
 *         Options for the element.
 *
 * Option Args:
 *     ariaLabel (string, optional):
 *         The ARIA label assigned to the element.
 *
 *     id (string, optional):
 *         The ID of the element.
 *
 *     hasCounters (boolean, optional):
 *         Whether this section contains counters.
 *
 * Returns:
 *     HTMLElement:
 *     The new element.
 */
BC19.makeSectionElement = function(options) {
    const sectionEl = document.createElement('section');
    sectionEl.classList.add('bc19-c-dashboard__section');

    if (options.hasCounters) {
        sectionEl.classList.add('-has-counters');
    }

    if (options.id) {
        sectionEl.id = options.id;
    }

    if (options.ariaLabel) {
        sectionEl.setAttribute('aria-label', options.ariaLabel);
    }

    return sectionEl;
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
    const graphEl = document.getElementById(options.bindto.substr(1));
    console.assert(graphEl);

    if (graphEl.offsetParent === null) {
        /* This graph is not currently shown. Schedule for later. */
        BC19.delayedScheduledGraphData.push(options);
        return;
    }

    const columns = options.data.columns;
    options.data.columns = [];

    const xTickOptions = options?.axis?.x?.tick || {};

    options = Object.assign({}, BC19.commonTimelineOptions, options);

    options.axis.x = {
        type: 'timeseries',
        localtime: false,
        label: {
            position: 'outer-left',
        },
        tick: {
            count: xTickOptions.count,
            culling: xTickOptions.culling || true,
            fit: (xTickOptions.fit !== false),
            format: '%b %d',
        },
        min: BC19.defaultTimelineDomain[0],
        max: BC19.defaultTimelineDomain[1],
    };

    if (!options.tooltip.format) {
        options.tooltip.format = {
            value: function(value, ratio, id, index) {
                if (index > 0) {
                    const prevValue =
                        this.data(id)[0].values[index - 1].value;

                    if (prevValue > value) {
                        return value + ' (-' + (prevValue - value) + ')';
                    } else if (prevValue < value) {
                        return value + ' (+' + (value - prevValue) + ')';
                    }
                }

                return value;
            }
        };
    }

    const graph = bb.generate(options);
    BC19.graphs.push(graph);

    BC19.scheduledGraphData.push([graph, columns]);

    return graph;
};


/**
 * Render the next timeline graph on the page.
 */
BC19.renderNextGraphData = function() {
    if (BC19.scheduledGraphData.length > 0) {
        const info = BC19.scheduledGraphData.shift();

        info[0].load({
            columns: info[1],
        });

        setTimeout(BC19.renderNextGraphData, 0);
    }
}


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
                const pct = Math.round((d.value / total) * 100);

                this.appendChild(d3.create('div')
                    .attr('class', 'bc19-c-bar-graph__pct')
                    .attr('id', 'bar_graph_' + d.data_id)
                    .text(Number.isNaN(pct) ? '' : `${pct}%`)
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
 *     color (string, optional):
 *         An explicit color to use for the value text.
 *
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
 *     isPct (boolean, optional):
 *         Whether the values represent percentages.
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
    const color = options.color;
    let formatValue = options.formatValue;

    if (!formatValue && options.isPct) {
        formatValue = BC19.formatPct;
    } else {
        formatValue = function(value) {
            return value.toLocaleString();
        }
    }

    let formatRelValue = options.formatRelValues;

    if (!formatRelValue && options.isPct) {
        formatRelValue = BC19.formatPctRel;
    } else {
        formatRelValue = function(value, relValue) {
            return formatValue(Math.abs(value - relValue));
        }
    }

    const valueEl = el.querySelector('.bc19-c-counter__value');
    valueEl.innerText = formatValue(value);

    if (color) {
        valueEl.style.color = color;
    }

    const relValues = options.relativeValues;

    if (relValues && relValues.length > 0) {
        const relativeValueEls =
            el.querySelectorAll('.bc19-c-counter__relative-value');
        console.assert(relativeValueEls.length >= relValues.length);

        for (let i = 0; i < relValues.length; i++) {
            const relValueEl = relativeValueEls[i];
            const relEl = relValueEl.parentNode;
            const relValue = relValues[i];

            if (relValue === null || isNaN(relValue)) {
                relValueEl.innerText = 'no data';
                continue;
            }

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

    BC19.scheduledGraphRangeUpdates = Array.from(BC19.graphs);
    BC19.updateNextTimelineDateRanges(domain);
};

BC19.updateNextTimelineDateRanges = function(domain) {
    if (BC19.scheduledGraphRangeUpdates.length > 0) {
        const graph = BC19.scheduledGraphRangeUpdates.shift();

        graph.axis.range({
            min: {
                x: domain[0],
            },
            max: {
                x: domain[1],
            },
        });

        requestAnimationFrame(() => BC19.updateNextTimelineDateRanges(domain),
                              0);
    }
}


/**
 * Return a timeline range using the specified number of days.
 *
 * Args:
 *     value (integer or string, optional):
 *         The number of days, or "all".
 *
 * Returns:
 *     Array:
 *     An array of ``[fromDate, toDate]``, as moment objects.
 */
BC19.getTimelineDateRange = function(value) {
    let fromMDate = BC19.lastDate;
    let toMDate = moment(BC19.lastMDate).add(1, 'days');

    if (value === undefined) {
        const dateSelectorEl = document.getElementById('date-selector');
        value = dateSelectorEl.value;
    }

    if (value === 'all') {
        fromMDate = moment(BC19.firstMDate);
    } else {
        fromMDate = moment(BC19.lastMDate).subtract(
            value.split('-')[1], 'days');
    }

    return [fromMDate, toMDate];
}


BC19.setupElements = function() {
    /* Show the report timestamp. */
    const timestampEl = document.getElementById('report-timestamp');
    timestampEl.innerText = BC19.reportTimestamp.format(
        'dddd, MMMM Do, YYYY @ h:mm a');

    /* Show the current monitoring tier. */
    const tier = BC19.monitoringTier;

    const tierSectionEl = document.getElementById('monitoring-tier-section');

    if (tierSectionEl) {
        tierSectionEl.classList.add(`-is-tier-${tier.toLowerCase()}`);

        const tierEl = document.getElementById('monitoring-tier');

        if (tierEl) {
            tierEl.innerText = tier;
        }
    }

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

    const showDiscontinuedEl = document.getElementById('show-discontinued');
    BC19.els.showDiscontinuedEl = showDiscontinuedEl;
    showDiscontinuedEl.addEventListener(
        'change',
        () => _onShowDiscontinuedChanged());


    if (showDiscontinuedEl.checked) {
        _onShowDiscontinuedChanged();
    }

    /* Update the dates in the counters. */
    const datesMap = {};

    document.querySelectorAll('.bc19-o-update-day').forEach(el => {
        const showWeeks = (el.dataset['showWeeks'] === '1');
        const key = el.dataset.key + (showWeeks ? '-weeks' : '');

        if (!datesMap.hasOwnProperty(key)) {
            const latestDate = BC19.latestRowDates[key];
            let text;

            if (showWeeks) {
                text = BC19.getWeeksText(latestDate);
            } else {
                text = BC19.getDayText(latestDate);
            }

            datesMap[key] = text;
        }

        el.innerText = datesMap[key];
    });

    document.getElementById('page-spinner').remove();

    const dashboardEl = document.querySelector('.bc19-c-dashboard');
    dashboardEl.classList.remove('-is-loading');

    BC19.els.sectionsContainer =
        dashboardEl.querySelector('.bc19-c-dashboard__sections');

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
BC19.loadDashboard = function(datasetPath, onLoad) {
    fetch(new Request(datasetPath + '?' + moment().format('x')))
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
        .then(onLoad)
    /*
        .catch(msg => {
            console.error(msg);
            alert(msg);
        });
        */
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

    rangeEl.classList.remove('-is-shown');

    const range = BC19.getTimelineDateRange(value);

    BC19.setDateRange(moment.max(range[0], BC19.firstMDate).toDate(),
                      moment.max(range[1], BC19.lastMDate).toDate());
}


function _onShowDiscontinuedChanged() {
    const showDiscontinuedEl = BC19.els.showDiscontinuedEl;

    document.body.classList.toggle('-show-discontinued',
                                   showDiscontinuedEl.checked);

    if (showDiscontinuedEl.checked &&
        BC19.delayedScheduledGraphData.length > 0) {
        BC19.delayedScheduledGraphData.forEach(
            graphOptions => BC19.setupBBGraph(graphOptions));

        BC19.delayedScheduledGraphData = [];
        BC19.renderNextGraphData();
    }
}
