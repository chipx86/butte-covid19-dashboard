BC19.Schools = {};


function setYear(year) {
}


function setupElements() {
    const yearSelectorEl = document.getElementById('school-year');
    const curSchoolYear = BC19.Schools.curSchoolYear;

    BC19.Schools.schoolYears.forEach(schoolYear => {
        const optionEl = document.createElement('option');
        optionEl.setAttribute('value', schoolYear);
        optionEl.innerText = `${schoolYear}-${schoolYear + 1}`;

        if (schoolYear == curSchoolYear) {
            optionEl.setAttribute('selected', '');
        }

        yearSelectorEl.options.add(optionEl);
    });

    yearSelectorEl.addEventListener(
        'change',
        () => {
            const urlParams = BC19.Schools.urlParams;

            urlParams.set('year', yearSelectorEl.value);
            window.location.search = urlParams.toString();
        });

    BC19.setupElements();
}


function setupCounters() {
    const data = BC19.countersData.countyWide;

    BC19.setCounter('student-cases-counter', data.studentCases);
    BC19.setCounter('staff-cases-counter', data.staffCases);
    BC19.setCounter('districts-with-cases-counter',
                    data.districtsWithNewCases);
    BC19.setCounter('schools-with-cases-counter',
                    data.schoolsWithNewCases);
}


function setupBarGraphs() {
    const data = BC19.barGraphsData;

    BC19.setupBarGraph(
        d3.select('#by_grade_level'),
        {
            pct: true,
        },
        data.casesByGradeLevel);

    BC19.setupBarGraph(
        d3.select('#by_district'),
        {
            pct: true,
        },
        data.casesByDistrict);
}


function setupTimelineGraph(options) {
    const tickCounts = BC19.tickCounts;
    const graphID = options.graphID;
    const maxValue = options.maxValue;

    const graphSize = (options.small
                       ? BC19.graphSizes.SMALL
                       : BC19.graphSizes.STANDARD);
    const tickCountsSize = (options.small
                            ? tickCounts.SMALL
                            : tickCounts.STANDARD);
    let labelOptions;
    const columns = options.columns;

    if (options.type === 'bar') {
        const mainDataID = columns[columns.length - 1][0];

        labelOptions = {
            format: {},
        };

        labelOptions.format[mainDataID] = function(v, id, i, j) {
            let total = 0;

            for (let colIndex = 1; colIndex < columns.length; colIndex++) {
                total += columns[colIndex][i + 1];
            }

            if (total > 0) {
                return total;
            }
        };
    }

    const graphOptions = {
        bindto: `#${graphID}`,
        size: {
            height: graphSize,
        },
        data: {
            x: 'date',
            colors: BC19.colors,
            columns: columns,
            names: options.names,
            order: null,
            groups: options.groups,
            type: options.type,
            labels: labelOptions,
        },
        grid: {
            y: {
                show: true,
            },
        },
        axis: {
            y: {
                max: BC19.getMaxY(maxValue, tickCountsSize),
                padding: 0,
                tick: {
                    stepSize: BC19.getStepSize(maxValue, tickCountsSize),
                },
            },
        },
        legend: {
            show: options.showLegend,
        },
        clipPath: false,
    };

    if (options.small) {
        graphOptions.axis.x = {
            tick: {
                count: 5,
            },
        };
        graphOptions.grid = {
            x: {
                show: false,
            },
        };
    }

    if (options.linkTooltip === false) {
        graphOptions.tooltip = {
            linked: false,
        };
    }

    BC19.setupBBGraph(graphOptions);
}


function setupTotalCasesGraph(options) {
    const graphData = options.graphData.total;

    options.columns = [
        BC19.graphData.dates,
        graphData.studentLocalCases,
        graphData.studentRemoteCases,
        graphData.staffLocalCases,
        graphData.staffRemoteCases,
    ];

    options.names = {
        students_local: 'Students (in person)',
        students_remote: 'Students (remote)',
        staff_local: 'Staff (in person)',
        staff_remote: 'Staff (remote)',
    };

    options.groups = [[
        'students_local',
        'students_remote',
        'staff_local',
        'staff_remote',
    ]];

    options.type = 'area';

    setupTimelineGraph(options);
}


function setupNewCasesGraph(options) {
    const graphData = options.graphData.newCases;

    options.columns = [
        BC19.graphData.dates,
        graphData.studentLocalCases,
        graphData.studentRemoteCases,
        graphData.staffLocalCases,
        graphData.staffRemoteCases,
    ];

    options.names = {
        new_students_local: 'Students (in person)',
        new_students_remote: 'Students (remote)',
        new_staff_local: 'Staff (in person)',
        new_staff_remote: 'Staff (remote)',
    };

    options.groups = [[
        'new_students_local',
        'new_students_remote',
        'new_staff_local',
        'new_staff_remote',
    ]];

    options.type = 'bar';

    setupTimelineGraph(options);
}


function setupCaseRateGraph(options) {
    const graphData = options.graphData.caseRate;

    options.columns = [
        BC19.graphData.dates,
        graphData.studentLocalCases,
        graphData.studentRemoteCases,
        graphData.staffLocalCases,
        graphData.staffRemoteCases,
    ];

    options.names = {
        case_rate_students_local: 'Students (in person)',
        case_rate_students_remote: 'Students (remote)',
        case_rate_staff_local: 'Staff (in person)',
        case_rate_staff_remote: 'Staff (remote)',
    };

    options.groups = [[
        'case_rate_students_local',
        'case_rate_students_remote',
        'case_rate_staff_local',
        'case_rate_staff_remote',
    ]];

    options.type = 'area';

    setupTimelineGraph(options);
}


function setupNewSection(options) {
    const parentEl = options.parentEl;
    const source = options.source;

    if (options.title) {
        const headerEl = BC19.makeSectionHeaderElement({
            id: options.id,
            title: options.title,
            subtitles: options.subtitles,
        });

        if (source) {
            headerEl.appendChild(BC19.makeSourcesElement([{
                url: source,
            }]));
        }

        if (options.headerChildren) {
            options.headerChildren.forEach(el => headerEl.appendChild(el));
        } else if (options.headerText) {
            options.headerText.forEach(html => {
                const paragraphEl = document.createElement('p');
                paragraphEl.innerHTML = html;
                headerEl.appendChild(paragraphEl);
            });
        }

        parentEl.appendChild(headerEl);
    }

    const sectionEl = BC19.makeSectionElement({
        ariaLabel: options.ariaLabel || `Graphs for ${options.title}`,
    });
    parentEl.appendChild(sectionEl);

    return sectionEl;
}


function makeTiles() {
    const tilesEl = document.createElement('div');
    tilesEl.classList.add('bc19-c-tiles');

    return tilesEl;
}


function makeTile(options) {
    const tileEl = document.createElement('div');
    tileEl.classList.add('bc19-c-tiles__tile');

    const titleEl = document.createElement('a');
    titleEl.classList.add('bc19-c-tiles__tile-header');
    titleEl.innerText = options.title;
    titleEl.setAttribute('href', `?${options.url}`);
    tileEl.appendChild(titleEl);

    const cases = options.cases;

    if (cases !== undefined) {
        if (cases === 0 && !options.casesHaveData) {
            options.subtitle = '0 cases or no data';
        } else if (cases === 1) {
            options.subtitle = '1 case';
        } else {
            options.subtitle = `${cases} cases`;
        }
    }

    if (options.subtitle) {
        const subtitleEl = document.createElement('div');
        subtitleEl.classList.add('bc19-c-tiles__tile-subtitle');
        subtitleEl.innerText = options.subtitle;
        tileEl.appendChild(subtitleEl);

        const deltaCases = options.deltaCases;

        if (deltaCases) {
            const deltaEl = document.createElement('span');
            deltaEl.classList.add('bc19-c-tiles__tile-delta');
            deltaEl.setAttribute('title', `${deltaCases} new cases`);
            deltaEl.innerText = deltaCases;
            subtitleEl.appendChild(deltaEl);
        }
    }

    return tileEl;
}


function compareGraphCaseSets(name1, maxValues1, name2, maxValues2) {
    const total1 = maxValues1.totalCases;
    const total2 = maxValues2.totalCases;

    if (total1 < total2) {
        return 1;
    } else if (total1 > total2) {
        return -1;
    } else {
        if (name1 < name2) {
            return -1;
        } else if (name1 > name2) {
            return 1;
        } else {
            return 0;
        }
    }
}


function addDistrictSections(parentEl) {
    const sectionEl = setupNewSection({
        parentEl: parentEl,
        title: 'Districts',
        headerText: [
            ('<em>If a district or school is not listed, it may not ' +
             'provide public case information.</em>'),
            'Click or tap a district name to see more information.',
        ],
    });

    const tilesEl = makeTiles();
    sectionEl.appendChild(tilesEl);

    const districts = BC19.Schools.districts;

    const sortedDistricts = Object.entries(districts).sort(
        (districtPair1, districtPair2) => compareGraphCaseSets(
            districtPair1[1],
            BC19.maxValues.districts[districtPair1[0]],
            districtPair2[1],
            BC19.maxValues.districts[districtPair2[0]]));

    const caseRelValues = {};

    BC19.barGraphsData.countyWide.casesByDistrict.forEach(data => {
        caseRelValues[data.data_id] = data.relValue;
    });

    sortedDistricts.forEach(districtPair => {
        const districtID = districtPair[0];
        const districtInfo = districtPair[1];
        const source = districtInfo.source;
        const districtMaxValues = BC19.maxValues.districts[districtID];

        const urlParams = new URLSearchParams(window.location.search);
        urlParams.set('district', districtID);

        const tileEl = makeTile({
            title: districtInfo.full_name,
            cases: districtMaxValues.totalCases,
            deltaCases: caseRelValues[districtID],
            url: urlParams.toString(),
        });
        tilesEl.appendChild(tileEl);

        const newGraphID = `${districtID}_new_cases_graph`;
        const newGraphEl = BC19.makeBBGraphElement({
            dataID: newGraphID,
        });
        tileEl.appendChild(newGraphEl);

        setupNewCasesGraph({
            graphID: newGraphID,
            graphData: BC19.graphData.districts[districtID],
            maxValue: BC19.maxValues.districts[districtID].newCases,
            showLegend: false,
            small: true,
            linkTooltip: false,
        });
    });
}


function addSchoolSections(parentEl, districtID) {
    const schools = BC19.Schools.schools[districtID];

    const sectionEl = setupNewSection({
        parentEl: parentEl,
        title: 'Schools',
        headerChildren: [
            document.createTextNode(
                'Click or tap a school name to see more information'
            ),
        ],
    });

    const tilesEl = makeTiles();
    sectionEl.appendChild(tilesEl);

    const sortedSchools = Object.entries(schools).sort(
        (schoolPair1, schoolPair2) => compareGraphCaseSets(
            schoolPair1[1],
            BC19.maxValues.schools[schoolPair1[0]],
            schoolPair2[1],
            BC19.maxValues.schools[schoolPair2[0]]));

    const caseRelValues = {};

    BC19.barGraphsData.districts[districtID].casesBySchool.forEach(data => {
        caseRelValues[data.data_id] = data.relValue;
    });

    const casesHaveData = (
        BC19.maxValues.districts[districtID].totalCases > 0);

    sortedSchools.forEach((schoolPair, i) => {
        const schoolID = schoolPair[0];

        if (!schools.hasOwnProperty(schoolID)) {
            return;
        }

        const schoolName = schoolPair[1];
        const schoolGraphs = BC19.graphData.schools[schoolID];
        const schoolMaxValues = BC19.maxValues.schools[schoolID];

        const urlParams = new URLSearchParams(window.location.search);
        urlParams.set('school', schoolID);

        const tileEl = makeTile({
            title: schoolName,
            cases: schoolMaxValues.totalCases,
            casesHaveData: casesHaveData,
            deltaCases: caseRelValues[schoolID],
            url: urlParams.toString(),
        });
        tilesEl.appendChild(tileEl);

        const newGraphID = `${schoolID}_new_cases_graph`;
        const newGraphEl = BC19.makeBBGraphElement({
            dataID: newGraphID,
        });
        tileEl.appendChild(newGraphEl);

        setupNewCasesGraph({
            graphID: newGraphID,
            graphData: schoolGraphs,
            maxValue: schoolMaxValues.newCases,
            showLegend: false,
            small: true,
            linkTooltip: false,
        });
    });
}


function setupGraphs() {
    const sectionsContainer = BC19.els.sectionsContainer;
    const tickCounts = BC19.tickCounts;
    const mode = BC19.Schools.mode;
    const school = BC19.Schools.curSchool;
    const district = BC19.Schools.curDistrict;
    let barGraphData;
    let counters;
    let graphData;
    let maxValues;
    let notice;

    const overviewTitleEl = document.getElementById('overview-title');

    if (mode === 'county') {
        barGraphData = BC19.barGraphsData.countyWide;
        counters = BC19.countersData.countyWide;
        graphData = BC19.graphData.countyWide;
        maxValues = BC19.maxValues.countyWide;

        overviewTitleEl.parentElement.removeChild(overviewTitleEl);
    } else if (mode === 'district') {
        barGraphData = BC19.barGraphsData.districts[district];
        counters = BC19.countersData.districts[district];
        graphData = BC19.graphData.districts[district];
        maxValues = BC19.maxValues.districts[district];
        notice = BC19.Schools.notices.districts[district];

        const districtName = BC19.Schools.districts[district].full_name;

        if (!BC19.Schools.isEmbedded) {
            const urlParams = new URLSearchParams(window.location.search);
            urlParams.delete('district');
            const allDistrictsURL = urlParams.toString();

            overviewTitleEl.innerHTML =
                `<h2>${districtName}</h2>` +
                `<a href="?${allDistrictsURL}">See all districts</a>`;
        }

        document.title = `${districtName} | ${document.title}`;
    } else if (mode === 'school') {
        barGraphData = {};
        counters = BC19.countersData.schools[school];
        graphData = BC19.graphData.schools[school];
        maxValues = BC19.maxValues.schools[school];
        notice = BC19.Schools.notices.districts[district];

        const districtName = BC19.Schools.districts[district].full_name;
        const schoolName = BC19.Schools.schools[district][school];

        if (!BC19.Schools.isEmbedded) {
            const urlParams = new URLSearchParams(window.location.search);
            urlParams.delete('school');
            const districtURL = urlParams.toString();

            urlParams.delete('district');
            const allDistrictsURL = urlParams.toString();

            overviewTitleEl.innerHTML =
                `<h2>${schoolName}</h2>` +
                `<h3><a href="?${districtURL}">${districtName}</a></h3>` +
                `<a href="?${allDistrictsURL}">See all districts</a>`;
        }

        document.title = `${schoolName} | ${document.title}`;
    }

    console.assert(maxValues);
    console.assert(graphData);

    if (notice) {
        overviewTitleEl.innerHTML += `<p class="bc19-c-notice">${notice}</p>`;
    }

    BC19.setCounter('student-cases-counter', counters.studentCases);
    BC19.setCounter('staff-cases-counter', counters.staffCases);

    if (counters.districtsWithNewCases) {
        BC19.setCounter('districts-with-cases-counter',
                        counters.districtsWithNewCases);
    } else {
        document.getElementById('districts-with-cases-counter')
            .setAttribute('style', 'display: none');
    }

    if (counters.schoolsWithNewCases) {
        BC19.setCounter('schools-with-cases-counter',
                        counters.schoolsWithNewCases);
    } else {
        document.getElementById('schools-with-cases-counter')
            .setAttribute('style', 'display: none');
    }

    if (barGraphData.casesByGradeLevel) {
        BC19.setupBarGraph(
            d3.select('#by_grade_level'),
            {
                pct: true,
            },
            barGraphData.casesByGradeLevel);
    } else {
        document.getElementById('by_grade_level')
            .setAttribute('style', 'display: none');
    }

    if (barGraphData.casesByDistrict) {
        BC19.setupBarGraph(
            d3.select('#by_district'),
            {
                pct: true,
            },
            barGraphData.casesByDistrict);
    } else {
        document.getElementById('by_district')
            .setAttribute('style', 'display: none');
    }

    /* TODO: Add a way to get back to district */

    setupTotalCasesGraph({
        graphID: 'total_cases_graph',
        graphData: graphData,
        maxValue: maxValues.totalCases,
    });
    setupNewCasesGraph({
        graphID: 'new_cases_graph',
        graphData: graphData,
        maxValue: maxValues.newCases,
    });
    setupCaseRateGraph({
        graphID: 'case_rate_graph',
        graphData: graphData,
        maxValue: maxValues.caseRate,
    });

    if (mode === 'county') {
        addDistrictSections(sectionsContainer);
    } else if (mode === 'district') {
        addSchoolSections(sectionsContainer, district);
    } else if (mode === 'school') {
        document.getElementById('overview-cases').classList.remove('-has-side');
    }
}


BC19.init = function() {
    BC19.loadDashboard(
        '/data/json/bc19-schools.1.min.json',
        data => {
            const urlParams = new URLSearchParams(window.location.search);
            const embed = urlParams.get('embed');
            const year = urlParams.get('year') ||
                         data.schoolYears[data.schoolYears.length - 1];
            const school = urlParams.get('school');
            const district = urlParams.get('district');

            let mode;

            if (school !== null) {
                mode = 'school';
            } else if (district !== null) {
                mode = 'district';
            } else {
                mode = 'county';
            }

            BC19.Schools.curSchoolYear = year;
            BC19.Schools.curDistrict = district;
            BC19.Schools.curSchool = school;
            BC19.Schools.districts = data.districts;
            BC19.Schools.mode = mode;
            BC19.Schools.notices = data.notices;
            BC19.Schools.schools = data.schools;
            BC19.Schools.schoolYears = data.schoolYears;
            BC19.Schools.urlParams = urlParams;
            BC19.Schools.isEmbedded = !!embed;

            BC19.processDashboardData({
                barGraphs: data.barGraphs[year],
                counters: data.counters[year],
                dates: data.dates[year],
                latestRows: data.latestRows[year],
                maxValues: data.maxValues[year],
                monitoringTier: data.monitoringTier,
                reportTimestamp: data.reportTimestamp,
                timelineGraphs: data.timelineGraphs[year],
            });

            if (embed) {
                document.body.classList.add('-is-embedded');
            }

            setupElements();

            setupGraphs();

            BC19.renderNextGraphData();
        });
};
