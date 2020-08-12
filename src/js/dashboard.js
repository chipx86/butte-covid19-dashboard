window.BC19 = {
    COUNTY_POPULATION: 219186,

    tickCounts: {
        VERY_TALL: 15,
        STANDARD: 10,
        MEDIUM: 9,
        SMALL: 5,
        VERY_SMALL: 5,
    },

    minDates: {
        testPositivityRate: '2020-04-10',
    },

    maxValues: {
        hospitalizations: 0,
        jailInmateCurCases: 0,
        jailInmatePopulation: 0,
        jailStaffTotalCases: 0,
        newCases: 0,
        newDeaths: 0,
        newSNFDeaths: 0,
        sevenDayPosRate: 0,
        totalCases: 0,
        totalDeaths: 0,
        tests: 0,
        twoWeekPosRate: 0,
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

    latestRows: {},

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


BC19.normRelValue = function(value, prevValue, hideNegative) {
    if (prevValue === null || (hideNegative && value < prevValue)) {
        return 0;
    }

    return value - prevValue;
};


BC19.processTimelineData = function(timeline) {
    const rows = timeline.dates;
    const graphDates = ['date'];

    const graphTotalCases = ['cases'];
    const graphNewCases = ['new_cases'];
    const graphTotalDeaths = ['total_deaths'];
    const graphNewDeaths = ['new_deaths'];
    const graphTwoWeekNewCaseRate = ['new_case_rate'];

    const graphTotalTests = ['total_tests'];
    const graphNewTests = ['new_tests'];
    const graphTotalTestResults = ['test_results'];
    const graphNegativeResults = ['neg_results'];
    const graphPositiveResults = ['pos_results'];
    const graphTestPositivityRate = ['test_pos_rate'];

    const graphCasesInBiggsGridley = ['biggs_gridley'];
    const graphCasesInChico = ['chico'];
    const graphCasesInDurham = ['durham'];
    const graphCasesInGridley = ['gridley'];
    const graphCasesInOroville = ['oroville'];
    const graphCasesInRidge = ['ridge'];
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
    const graphNursingNewPatientDeaths = ['new_patient_deaths'];
    const graphNursingNewStaffDeaths = ['new_staff_deaths'];

    const graphJailPop = ['jail_inmate_pop'];
    const graphJailInmateTests = ['jail_inmate_tests'];
    const graphJailInmatePosResults = ['jail_inmate_pos_results'];
    const graphJailInmateCurCases = ['jail_inmate_cur_cases'];
    const graphJailStaffTests = ['jail_staff_tests'];
    const graphJailStaffTotalCases = ['jail_staff_total_cases'];

    const graphNotes = [];

    let maxJailInmateCurCases = 0;
    let maxJailInmatePopulation = 0;
    let maxJailStaffTotalCases = 0;
    let maxNewCases = 0;
    let maxNewDeaths = 0;
    let maxHospitalizationsY = 0;
    let maxCurrentSNFCases = 0;
    let maxNewSNFDeaths = 0;
    let maxTwoWeekCaseRate = 0;
    let maxSevenDayPosRate = 0;
    let maxViralTests = 0;

    let latestAgeDataRow;
    let latestCasesRow;
    let latestCountyHospitalDataRow;
    let latestDeathsRow;
    let latestIsolationDataRow;
    let latestJailRow;
    let latestPerHospitalDataRow;
    let latestRegionDataRow;
    let latestStateHospitalsRow;
    let latestTestPosDataRow;

    const minTestPositivityRateDate = BC19.minDates.testPositivityRate;
    let foundMinTestPositivityRateDate = false;

    ageRangeKeys.forEach(key => {
        graphCasesByAge[key] = [`age_${key.replace('-', '_')}`];
    });

    for (let i = 0; i < rows.length; i++) {
        const row = rows[i];

        row.i = i;
        graphDates.push(row.date);

        const confirmedCases = row.confirmed_cases;
        const deltaConfirmedCases = Math.max(confirmedCases.delta_total, 0);
        const viralTests = row.viral_tests;
        const viralTestResults = viralTests.results;
        const regions = row.regions;
        const ageRanges = row.age_ranges_in_years;
        const countyHospital = row.hospitalizations.county_data;
        const stateHospital = row.hospitalizations.state_data;
        const snf = row.skilled_nursing_facilities;
        const prevDay = rows[i - 1];
        const twoWeeksAgo = rows[i - 14];
        const sevenDaysAgo = rows[i - 7];


        /* Confirmed Csses */
        graphTotalCases.push(confirmedCases.total);
        graphNewCases.push(deltaConfirmedCases);

        if (confirmedCases.total !== null) {
            latestCasesRow = row;
        }


        /* Deaths */
        graphTotalDeaths.push(row.deaths.total);
        graphNewDeaths.push(row.deaths.delta_total);

        maxNewDeaths = Math.max(maxNewDeaths, row.deaths.delta_total);

        if (deltaConfirmedCases && deltaConfirmedCases > maxNewCases) {
            maxNewCases = confirmedCases.delta_total;
        }

        if (row.deaths.total !== null) {
            latestDeathsRow = row;
        }


        /* 14-Day New Case Rate */
        const twoWeekCaseRateI1 = i - 14;
        let twoWeekCaseRate = null;

        if (twoWeekCaseRateI1 >= 0) {
            const twoWeekCaseRateRow1 = rows[twoWeekCaseRateI1];
            const twoWeekCaseRateRow2 = rows[i];
            const twoWeekCaseRateTotal1 =
                twoWeekCaseRateRow1.confirmed_cases.total;
            const twoWeekCaseRateTotal2 =
                twoWeekCaseRateRow2.confirmed_cases.total;

            if (twoWeekCaseRateTotal1 !== null &&
                twoWeekCaseRateTotal2 !== null) {
                twoWeekCaseRate = twoWeekCaseRateTotal2 -
                                  twoWeekCaseRateTotal1;
                maxTwoWeekCaseRate = Math.max(maxTwoWeekCaseRate,
                                              twoWeekCaseRate);
            }
        }

        graphTwoWeekNewCaseRate.push(twoWeekCaseRate);


        /* Testing Data */
        graphTotalTests.push(viralTests.total);
        graphNewTests.push(viralTests.delta_total);
        graphTotalTestResults.push(viralTests.results);

        if (viralTestResults && deltaConfirmedCases !== null) {
            graphNegativeResults.push(viralTestResults - deltaConfirmedCases);
            graphPositiveResults.push(deltaConfirmedCases);
        } else {
            graphNegativeResults.push(0);
            graphPositiveResults.push(0);
        }

        if (viralTests.total !== null) {
            maxViralTests = Math.max(maxViralTests, viralTests.delta_total);
        }

        if (viralTestResults !== null) {
            maxViralTests = Math.max(maxViralTests, viralTestResults);
        }


        /* Cases By Region */
        graphCasesInBiggsGridley.push(regions.biggs_gridley.cases);
        graphCasesInChico.push(regions.chico.cases);
        graphCasesInDurham.push(regions.durham.cases);
        graphCasesInOroville.push(regions.oroville.cases);
        graphCasesInRidge.push(regions.ridge.cases);
        graphCasesInGridley.push(regions.gridley.cases);
        graphCasesInOtherRegion.push(regions.other.cases);

        if (regions.chico.cases !== null) {
            latestRegionDataRow = row;
        }


        /* Cases By Age Group */
        let foundAge = false;

        ageRangeKeys.forEach(key => {
            const age = ageRanges[ageRangeInfo[key].sourceKey];
            graphCasesByAge[key].push(age);

            if (age !== null) {
                foundAge = true;
            }
        });

        if (foundAge) {
            latestAgeDataRow = row;
        }


        /* People In Isolation */
        graphInIsolation.push(row.in_isolation.current);
        graphReleasedFromIsolation.push(row.in_isolation.total_released);

        if (row.in_isolation.current !== null) {
            latestIsolationDataRow = row;
        }


        /* Hospitalizations */
        graphHospitalizations.push(stateHospital.positive);
        graphICU.push(stateHospital.icu_positive);
        graphHospitalizedResidents.push(countyHospital.hospitalized);

        maxHospitalizationsY = Math.max(maxHospitalizationsY,
                                        stateHospital.positive,
                                        countyHospital.hospitalized);

        if (countyHospital.hospitalized !== null) {
            latestCountyHospitalDataRow = row;
        }

        if (stateHospital.positive !== null) {
            latestStateHospitalsRow = row;
        }

        if (stateHospital.enloe_hospital !== null) {
            latestPerHospitalDataRow = row;
        }


        /* Skilled Nursing Facilities */
        graphNursingCurPatientCases.push(snf.current_patient_cases);
        graphNursingCurStaffCases.push(snf.current_staff_cases);
        graphNursingTotalPatientDeaths.push(snf.total_patient_deaths);
        graphNursingTotalStaffDeaths.push(snf.total_staff_deaths);

        let newSNFPatientDeaths;
        let newSNFStaffDeaths;

        if (i > 0 &&
            snf.total_patient_deaths !== null &&
            snf.total_staff_deaths !== null) {
            const prevSNF = prevDay.skilled_nursing_facilities;
            newSNFPatientDeaths =
                snf.total_patient_deaths - (prevSNF.total_patient_deaths || 0);
            newSNFStaffDeaths =
                snf.total_staff_deaths - (prevSNF.total_staff_deaths || 0);
        } else {
            newSNFPatientDeaths = snf.total_patient_deaths;
            newSNFStaffDeaths = snf.total_staff_deaths;
        }

        graphNursingNewPatientDeaths.push(newSNFPatientDeaths);
        graphNursingNewStaffDeaths.push(newSNFStaffDeaths);

        if (newSNFStaffDeaths !== null && newSNFStaffDeaths !== null) {
            maxNewSNFDeaths = Math.max(maxNewSNFDeaths,
                                       newSNFPatientDeaths + newSNFStaffDeaths);
        }

        if (snf.current_patient_cases !== null &&
            snf.current_staff_cases !== null) {
            maxCurrentSNFCases = Math.max(
                maxCurrentSNFCases,
                (snf.current_patient_cases + snf.current_staff_cases));
        }


        /* 7-Day Test Positivity Rate */
        if (!foundMinTestPositivityRateDate &&
            row.date === minTestPositivityRateDate) {
            foundMinTestPositivityRateDate = true;
        }

        if (foundMinTestPositivityRateDate &&
            confirmedCases.total !== null &&
            viralTests.total !== null &&
            sevenDaysAgo.confirmed_cases.total !== null &&
            sevenDaysAgo.viral_tests.total !== null &&
            graphTestPositivityRate[i + 1] !== null) {
            const posRate =
                (confirmedCases.total - sevenDaysAgo.confirmed_cases.total) /
                (viralTests.total - sevenDaysAgo.viral_tests.total) *
                100.0;

            graphTestPositivityRate.push(posRate);

            maxSevenDayPosRate = Math.max(maxSevenDayPosRate, posRate);
            latestTestPosDataRow = row;
        } else {
            graphTestPositivityRate.push(null);
        }


        /* Notable Event */
        if (row.note) {
            graphNotes.push({
                value: row.date,
                text: row.note,
            });
        }


        /* County Jail */
        const jailInmateCurCases = row.county_jail.inmates.current_cases;
        const jailInmatePopulation = row.county_jail.inmates.population
        const jailStaffTotalCases = row.county_jail.staff.total_positive;
        graphJailPop.push(jailInmatePopulation);
        graphJailInmateTests.push(row.county_jail.inmates.total_tests);
        graphJailInmatePosResults.push(row.county_jail.inmates.total_positive);
        graphJailInmateCurCases.push(jailInmateCurCases);
        graphJailStaffTests.push(row.county_jail.staff.total_tests);
        graphJailStaffTotalCases.push(jailStaffTotalCases);

        if (jailInmateCurCases !== null) {
            maxJailInmateCurCases = Math.max(maxJailInmateCurCases,
                                             jailInmateCurCases);
        }

        if (jailInmatePopulation !== null) {
            maxJailInmatePopulation = Math.max(maxJailInmatePopulation,
                                               jailInmatePopulation);
        }

        if (jailStaffTotalCases !== null) {
            maxJailStaffTotalCases = Math.max(maxJailStaffTotalCases,
                                              jailStaffTotalCases);
        }

        if (row.county_jail.inmates.population !== null) {
            latestJailRow = row;
        }
    }

    if (latestCasesRow === null) {
        throw new Error(
            "Oh no! The latest COVID-19 case data couldn't be " +
            "found! Please report this :)");
    }

    if (latestStateHospitalsRow === null) {
        throw new Error(
            "Oh no! The latest COVID-19 hospitals data couldn't be " +
            "found! Please report this :)");
    }

    if (latestJailRow === null) {
        throw new Error(
            "Oh no! The latest COVID-19 jail data couldn't be " +
            "found! Please report this :)");
    }

    BC19.latestRows = {
        ages: latestAgeDataRow,
        cases: latestCasesRow,
        countyHospitals: latestCountyHospitalDataRow,
        deaths: latestDeathsRow,
        jail: latestJailRow,
        isolation: latestIsolationDataRow,
        perHospital: latestPerHospitalDataRow,
        regions: latestRegionDataRow,
        stateHospitals: latestStateHospitalsRow,
        testPosRate: latestTestPosDataRow,
        tests: latestTestPosDataRow,
    };

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
        jailInmateCurCases: maxJailInmateCurCases,
        jailInmatePopulation: maxJailInmatePopulation,
        jailStaffTotalCases: maxJailStaffTotalCases,
        newCases: maxNewCases,
        newDeaths: maxNewDeaths,
        totalCases: latestCasesRow.confirmed_cases.total,
        totalDeaths: latestCasesRow.deaths.total,
        hospitalizations: maxHospitalizationsY,
        snf: maxCurrentSNFCases,
        newSNFDeaths: maxNewSNFDeaths,
        sevenDayPosRate: maxSevenDayPosRate,
        twoWeekCaseRate: maxTwoWeekCaseRate,
        viralTests: maxViralTests,
    };

    BC19.graphData = {
        dates: graphDates,
        notes: graphNotes,
        deaths: {
            totalDeaths: graphTotalDeaths,
            newDeaths: graphNewDeaths,
        },
        cases: {
            totalCases: graphTotalCases,
            newCases: graphNewCases,
            twoWeekNewCaseRate: graphTwoWeekNewCaseRate,
        },
        jail: {
            inmatePopulation: graphJailPop,
            inmateTests: graphJailInmateTests,
            inmatePosResults: graphJailInmatePosResults,
            inmateCurCases: graphJailInmateCurCases,
            staffTests: graphJailStaffTests,
            staffTotalCases: graphJailStaffTotalCases,
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
            biggsGridley: graphCasesInBiggsGridley,
            chico: graphCasesInChico,
            durham: graphCasesInDurham,
            gridley: graphCasesInGridley,
            oroville: graphCasesInOroville,
            ridge: graphCasesInRidge,
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
            newPatientDeaths: graphNursingNewPatientDeaths,
            newStaffDeaths: graphNursingNewStaffDeaths,
        },
    };
};


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


BC19.getMaxY = function(maxValue, numTicks) {
    const stepSize = BC19.getStepSize(maxValue, numTicks);

    return Math.ceil((maxValue / stepSize)) * stepSize;
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


BC19.setCounterFromRows = function(elID, options) {
    const latestRow = options.latestRow;
    const rowI = latestRow.i;
    const deltaDays = options.deltaDays;
    const getValue = options.getValue;
    const dates = BC19.timeline.dates;
    const relativeValues = [];

    deltaDays.forEach(numDays => {
        relativeValues.push(getValue(dates[rowI - numDays]));
    });

    BC19.setCounter(elID, {
        value: getValue(latestRow),
        relativeValues: relativeValues,
    });
};


BC19.setupCounters = function(timeline) {
    const casesRow = BC19.latestRows.cases;
    const isolationRow = BC19.latestRows.isolation;
    const stateHospitalsRow = BC19.latestRows.stateHospitals;
    const jailRow = BC19.latestRows.jail;
    const testsRow = BC19.latestRows.tests;
    const testPosRateRow = BC19.latestRows.testPosRate;
    const jailI = jailRow.i;
    const testPosRateI = testPosRateRow.i;
    const totalTests = testsRow.viral_tests.total;

    BC19.setCounterFromRows(
        'total-cases-counter',
        {
            latestRow: casesRow,
            getValue: row => row.confirmed_cases.total,
            deltaDays: [1, 7, 14, 30],
        });

    BC19.setCounterFromRows(
        'deaths-counter',
        {
            latestRow: casesRow,
            getValue: row => row.deaths.total,
            deltaDays: [1],
        });

    BC19.setCounterFromRows(
        'in-isolation-counter',
        {
            latestRow: isolationRow,
            getValue: row => row.in_isolation.current,
            deltaDays: [1, 7, 14, 30],
        });

    BC19.setCounterFromRows(
        'hospitalized-residents-counter',
        {
            latestRow: BC19.latestRows.countyHospitals,
            getValue: row => row.hospitalizations.county_data.hospitalized,
            deltaDays: [1],
        });

    BC19.setCounterFromRows(
        'hospitalized-counter',
        {
            latestRow: stateHospitalsRow,
            getValue: row => row.hospitalizations.state_data.positive,
            deltaDays: [1],
        });

    BC19.setCounterFromRows(
        'icu-counter',
        {
            latestRow: stateHospitalsRow,
            getValue: row => row.hospitalizations.state_data.icu_positive,
            deltaDays: [1],
        });

    BC19.setCounterFromRows(
        'total-tests-counter',
        {
            latestRow: testsRow,
            getValue: row => row.viral_tests.total,
            deltaDays: [1],
        });

    BC19.setCounterFromRows(
        'positive-test-results-counter',
        {
            latestRow: casesRow,
            getValue: row => row.confirmed_cases.total,
            deltaDays: [1],
        });

    BC19.setCounter(
        'positive-test-rate-counter',
        {
            value: BC19.graphData.viralTests.testPositivityRate
                [testPosRateI + 1],
            relativeValues: [
                BC19.graphData.viralTests.testPositivityRate[testPosRateI],
            ],
            formatValue: value => value.toFixed(2) + '%',
            formatRelValues: [
                (value, relValue) => {
                    return Math.abs(value - relValue).toFixed(2) + '%';
                },
            ],
        });

    BC19.setCounter(
        'county-population-counter',
        {
            value: BC19.COUNTY_POPULATION,
        });

    BC19.setCounter(
        'pop-tested-pct-counter',
        {
            value: (totalTests / BC19.COUNTY_POPULATION * 100).toFixed(2),
            formatValue: value => '< ' + value + '%',
        });

    BC19.setCounter(
        'pop-not-tested-pct-counter',
        {
            value: (totalTests / BC19.COUNTY_POPULATION * 100).toFixed(2),
            formatValue: value => '> ' + (100 - value) + '%',
        });


    BC19.setCounterFromRows(
        'jail-inmate-pop-counter',
        {
            latestRow: jailRow,
            getValue: row => row.county_jail.inmates.population,
            deltaDays: [1],
        });

    BC19.setCounterFromRows(
        'jail-inmate-total-tests',
        {
            latestRow: jailRow,
            getValue: row => row.county_jail.inmates.total_tests,
            deltaDays: [1],
        });

    BC19.setCounterFromRows(
        'jail-inmate-cur-cases',
        {
            latestRow: jailRow,
            getValue: row => row.county_jail.inmates.current_cases,
            deltaDays: [1],
        });

    BC19.setCounter(
        'jail-inmate-pos-rate',
        {
            value: (BC19.graphData.jail.inmateCurCases[jailI + 1] /
                    BC19.graphData.jail.inmatePopulation[jailI + 1]) * 100,
            relativeValues: [
                BC19.graphData.jail.inmateCurCases[jailI] /
                BC19.graphData.jail.inmatePopulation[jailI] * 100,
            ],
            formatValue: value => value.toFixed(2) + '%',
            formatRelValues: [
                (value, relValue) => {
                    return Math.abs(value - relValue).toFixed(2) + '%';
                },
            ],
        });

    BC19.setCounterFromRows(
        'jail-staff-total-tests',
        {
            latestRow: jailRow,
            getValue: row => row.county_jail.staff.total_tests,
            deltaDays: [1],
        });

    BC19.setCounterFromRows(
        'jail-staff-total-cases',
        {
            latestRow: jailRow,
            getValue: row => row.county_jail.staff.total_positive,
            deltaDays: [1],
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
    const agesI = BC19.latestRows.ages.i + 1;

    BC19.setupBarGraph(
        d3.select('#by_age_graph'),
        {},
        BC19.visibleAgeRanges.map(key => {
            const ageRanges = BC19.graphData.ageRanges[key];
            const ageRangeInfo = BC19.ageRangeInfo[key];
            const value = ageRanges[agesI];

            return {
                data_id: key,
                label: ageRangeInfo.text || key.replace('_', '-'),
                value: value,
                relValue: BC19.normRelValue(value, ageRanges[agesI - 1]),
            };
        }));
};


BC19.setupByRegionGraph = function(timeline) {
    const row = BC19.latestRows.regions;
    const regions = row.regions;
    const prevIndex = row.i - 1;
    const prevRegions = timeline.dates[prevIndex].regions;

    BC19.setupBarGraph(
        d3.select('#by_region_graph'),
        {},
        [
            {
                data_id: 'biggs_gridley',
                label: 'Biggs, Gridley',
                value: regions.biggs_gridley.cases,
                relValue: BC19.normRelValue(regions.biggs_gridley.cases,
                                            prevRegions.biggs_gridley.cases),
            },
            {
                data_id: 'chico',
                label: 'Chico',
                value: regions.chico.cases,
                relValue: BC19.normRelValue(regions.chico.cases,
                                            prevRegions.chico.cases),
            },
            {
                data_id: 'durham',
                label: 'Durham',
                value: regions.durham.cases,
                relValue: BC19.normRelValue(regions.durham.cases,
                                            prevRegions.durham.cases),
            },
            {
                data_id: 'oroville',
                label: 'Oroville',
                value: regions.oroville.cases,
                relValue: BC19.normRelValue(regions.oroville.cases,
                                            prevRegions.oroville.cases),
            },
            {
                data_id: 'ridge',
                label: 'Paradise, Magalia...',
                value: regions.ridge.cases,
                relValue: BC19.normRelValue(regions.ridge.cases,
                                            prevRegions.ridge.cases),
            },
            {
                data_id: 'other',
                label: 'Other',
                value: regions.other.cases,
                relValue: BC19.normRelValue(regions.other.cases,
                                            prevRegions.other.cases,
                                            true),
            },
        ]);
};


BC19.setupByHospitalGraph = function(timeline) {
    const row = BC19.latestRows.perHospital;
    const prevIndex = row.i - 1;
    const data = row.hospitalizations.state_data;
    const prevData = timeline.dates[prevIndex].hospitalizations.state_data;

    BC19.setupBarGraph(
        d3.select('#by_hospital_graph'),
        {},
        [
            {
                data_id: 'enloe',
                label: 'Enloe Hospital',
                value: data.enloe_hospital,
                relValue: BC19.normRelValue(data.enloe_hospital,
                                            prevData.enloe_hospital),
            },
            {
                data_id: 'oroville',
                label: 'Oroville Hospital',
                value: data.oroville_hospital,
                relValue: BC19.normRelValue(data.oroville_hospital,
                                            prevData.oroville_hospital),
            },
            {
                data_id: 'orchard',
                label: 'Orchard Hospital',
                value: data.orchard_hospital,
                relValue: BC19.normRelValue(data.orchard_hospital,
                                            prevData.orchard_hospital),
            },
        ]);
};


BC19.setupMainTimelineGraphs = function(timeline) {
    const graphData = BC19.graphData;
    const maxValues = BC19.maxValues;
    const tickCounts = BC19.tickCounts;
    const isolationData = graphData.isolation;
    const casesRow = BC19.latestRows.cases;
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
        bindto: '#two_week_new_case_rate_graph',
        size: {
            height: BC19.graphSizes.STANDARD,
        },
        data: {
            x: 'date',
            colors: BC19.colors,
            columns: [
                graphData.dates,
                graphData.cases.twoWeekNewCaseRate,
            ],
            names: {
                new_case_rate: 'New Cases Past 14 Days',
            },
            types: {
                new_case_rate: 'area',
            },
        },
        grid: {
            x: {
                lines: [
                    {
                        /*
                         * 3 day state calculation lag +
                         * 1 day state reporting lag+
                         */
                        value: moment().subtract(4, 'days')
                            .format('YYYY-MM-DD'),
                        text: 'Rough value considered by state',
                        position: 'start',
                    },
                ],
            },
            y: {
                show: true,
                lines: [
                    {
                        value: per1KPopRound,
                        text: 'May qualify to be on a monitoring list at ~' +
                              per1KPopRound + ' cases',
                        position: 'start',
                    },
                ],
            },
        },
        axis: {
            x: axisX,
            y: {
                max: BC19.getMaxY(Math.max(per1KPopRound + 20,
                                           maxValues.twoWeekCaseRate),
                                  tickCounts.STANDARD),
                padding: 0,
                tick: {
                    stepSize: BC19.getStepSize(maxValues.twoWeekCaseRate,
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
            ].concat(Object.values(graphData.ageRanges)),
            names: {
                age_0_17: '0-17',
                age_18_24: '18-24',
                age_25_34: '25-34',
                age_35_44: '35-44',
                age_45_54: '45-54',
                age_55_64: '55-64',
                age_65_74: '65-74',
                age_75_plus: '75+',

                age_18_49: '18-49 (Historical)',
                age_50_64: '50-64 (Historical)',
                age_65_plus: '65+ (Historical)',
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
        grid: {
            x: {
                lines: [
                    {
                        /*
                         * 7 *previous* day state calculation lag +
                         * 1 day reporting lag
                         */
                        value: moment().subtract(9, 'days')
                            .format('YYYY-MM-DD'),
                        text: 'Rough value considered by state',
                        position: 'start',
                    },
                ],
            },
            y: {
                show: true,
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


    /* Update the dates in the counters. */
    const datesMap = {};

    document.querySelectorAll('.bc19-o-update-day').forEach(el => {
        const key = el.dataset.key;

        if (!datesMap.hasOwnProperty(key)) {
            datesMap[key] = BC19.getDayText(BC19.latestRows[key].date);
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
            console.error(msg);
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
