// Эта строка должна появиться в консоли первой. Если её нет - файл не загружается.
console.log("ThermoGrid: app.js скрипт запущен.");

document.addEventListener('DOMContentLoaded', function() {
    let selectedDeviceId = null;
    let devicesList = [];
    let filteredDevices = [];
    let currentView = 'dashboard';
    let temperatureChart = null;
    let selectedPeriod = 1; // В часах или 'all'
    let timeOffset = 0; // Смещение времени для навигации (в часах)
    let dragHandlersAttached = false; // чтобы не дублировать обработчики при пересоздании графика
    let maxPointsSetting = 1000; // по умолчанию
    // removed approx smoothing feature

    // Persist hidden series per device across period changes
    const hiddenKey = (deviceId) => `hiddenSeries:${deviceId}`;
    const getHiddenSet = (deviceId) => {
        try {
            const raw = localStorage.getItem(hiddenKey(deviceId));
            const arr = raw ? JSON.parse(raw) : [];
            return new Set(arr.map(x => String(x)));
        } catch (_) { return new Set(); }
    };
    const saveHiddenSet = (deviceId, set) => {
        try { localStorage.setItem(hiddenKey(deviceId), JSON.stringify(Array.from(set))); } catch (_) {}
    };

    const devicesListEl = document.getElementById('devices-list');
    const navButtons = document.querySelectorAll('.nav-button');
    const views = document.querySelectorAll('.view');
    const chartCanvas = document.getElementById('temperatureChart');

    // Перестраиваем шапку списка устройств: метка, chip фильтра, кнопки
    const sidebarHeader = document.querySelector('.sidebar-header');
    sidebarHeader.innerHTML = '';

    const headerLeft = document.createElement('div');
    headerLeft.style.display = 'flex';
    headerLeft.style.alignItems = 'center';
    headerLeft.style.gap = '8px';
    const headerLabel = document.createElement('span');
    headerLabel.className = 'sidebar-header-label';
    const filterChip = document.createElement('span');
    filterChip.className = 'filter-chip';
    filterChip.style.display = 'none';
    headerLeft.appendChild(headerLabel);
    headerLeft.appendChild(filterChip);

    const headerRight = document.createElement('div');
    headerRight.style.display = 'flex';
    headerRight.style.alignItems = 'center';
    headerRight.style.gap = '6px';
    const filterBtn = document.createElement('button');
    filterBtn.className = 'sidebar-filter-btn';
    filterBtn.title = 'Фильтр';
    filterBtn.textContent = '🔍';
    const clearBtn = document.createElement('button');
    clearBtn.className = 'sidebar-filter-btn sidebar-filter-clear';
    clearBtn.title = 'Очистить фильтр';
    clearBtn.textContent = '✖';
    clearBtn.style.display = 'none';
    headerRight.appendChild(filterBtn);
    headerRight.appendChild(clearBtn);

    sidebarHeader.appendChild(headerLeft);
    sidebarHeader.appendChild(headerRight);

    let filterExpr = '';

    function updateFilterUI() {
        const now = Math.floor(Date.now() / 1000);
        const activeCount = filteredDevices.filter(d => (d.last_seen ? (now - d.last_seen) <= 300 : false)).length;
        headerLabel.textContent = `Devices (active ${activeCount})`;
        if (filterExpr) {
            filterChip.textContent = filterExpr;
            filterChip.style.display = 'inline-block';
            filterBtn.classList.add('active');
            clearBtn.style.display = 'inline-block';
            filterBtn.title = `Фильтр: ${filterExpr}`;
        } else {
            filterChip.style.display = 'none';
            filterBtn.classList.remove('active');
            clearBtn.style.display = 'none';
            filterBtn.title = 'Фильтр';
        }
    }

    filterBtn.addEventListener('click', () => {
        const value = prompt('Фильтр:\n- по имени/ID/IP: часть строки\n- по температуре: t>25.5 или t<21');
        filterExpr = (value || '').trim();
        filteredDevices = devicesList.filter(deviceMatchesFilter);
        if (selectedDeviceId && !filteredDevices.find(d => d.id === selectedDeviceId)) {
            selectedDeviceId = filteredDevices[0]?.id || null;
        }
        renderDevicesList();
        updateCurrentView();
    });

    clearBtn.addEventListener('click', () => {
        if (!filterExpr) return;
        filterExpr = '';
        filteredDevices = devicesList.slice();
        renderDevicesList();
        updateCurrentView();
    });

    function deviceMatchesFilter(device) {
        if (!filterExpr) return true;
        const v = filterExpr.toLowerCase();
        // Температурные фильтры t> / t< (по последнему чтению любых сенсоров)
        const tMatch = v.match(/^t\s*([<>])\s*(\d+(?:[\.,]\d+)?)$/i);
        if (tMatch) {
            const op = tMatch[1];
            const thr = parseFloat(tMatch[2].replace(',', '.'));
            // Темп фильтруем по наличию любого сенсора у устройства в карточках справа (данные загружаются позже),
            // поэтому ограничимся по статусу alarm_threshold_c, если есть. Иначе пропустим всех.
            if (device.alarm_threshold_c != null) {
                return op === '>' ? device.alarm_threshold_c > thr : device.alarm_threshold_c < thr;
            }
            return true;
        }
        // Текстовый фильтр по имени/ID/IP/MAC
        const fields = [device.deviceName, device.id, device.ip_address];
        return fields.some(x => (x || '').toString().toLowerCase().includes(v));
    }

    async function fetchDevicesList() {
        try {
            devicesList = await (await fetch('/api/devices')).json();
            filteredDevices = devicesList.filter(deviceMatchesFilter);
            if (!selectedDeviceId && filteredDevices.length > 0) {
                selectedDeviceId = filteredDevices[0].id;
            } else if (selectedDeviceId && !filteredDevices.find(d => d.id === selectedDeviceId)) {
                selectedDeviceId = filteredDevices[0]?.id || null;
            }
            renderDevicesList();
            updateCurrentView();
            
            // Если список устройств пуст, показываем сообщение "Ожидание данных"
            if (devicesList.length === 0) {
                document.getElementById('device-info-panel').innerHTML = '<div class="device-info-item">Ожидание данных...</div>';
                document.getElementById('sensors-cards').innerHTML = '';
                showEmptyChart("Ожидание данных...\nУстройства появятся после подключения к серверу");
            }
        } catch (error) {
            console.error("Error fetching devices list:", error);
            devicesListEl.innerHTML = '<h2>Devices</h2><p>Error loading devices.</p>';
        }
    }

    function renderDevicesList() {
        const devicesContainer = document.getElementById('devices-list');
        updateFilterUI();
        // Удаляем все элементы кроме заголовка
        Array.from(devicesContainer.children).forEach(el => {
            if (!el.classList.contains('sidebar-header')) el.remove();
        });
        
        if (filteredDevices.length === 0) {
            // Пусто без плейсхолдера
            return;
        }
        
        filteredDevices.forEach(device => {
            const card = document.createElement('div');
            let statusClass = 'status-green';
            if (device.alarm_active) statusClass = 'status-red';
            else if (!device.ip_address) statusClass = 'status-orange';
            
            card.className = `device-card ${statusClass} ${device.id === selectedDeviceId ? 'selected' : ''}`;
            card.innerHTML = `
                <div class="device-name">${device.deviceName || device.id}</div>
                <div class="device-ip">${device.ip_address || 'Offline'}</div>
            `;
            card.onclick = () => {
                if (selectedDeviceId !== device.id) {
                    selectedDeviceId = device.id;
                    renderDevicesList();
                    updateCurrentView();
                }
            };
            devicesContainer.appendChild(card);
        });
    }

    function showView(viewId) {
        currentView = viewId;
        views.forEach(v => v.classList.remove('active'));
        document.getElementById(`${viewId}-view`).classList.add('active');
        navButtons.forEach(b => b.classList.toggle('active', b.dataset.view === viewId));
        updateCurrentView();
    }

    async function updateCurrentView() {
        if (currentView === 'settings') {
            renderSettingsView();
            return;
        }
        
        // Если нет устройств вообще, показываем "Ожидание данных"
        if (devicesList.length === 0) {
            document.getElementById('device-info-panel').innerHTML = '<div class="device-info-item">Ожидание данных...</div>';
            document.getElementById('sensors-cards').innerHTML = '';
            showEmptyChart("Ожидание данных...\nУстройства появятся после подключения к серверу");
            return;
        }
        
        // Если есть устройства, но не выбрано, предлагаем выбрать
        if (!selectedDeviceId) {
            document.getElementById('device-info-panel').innerHTML = '<div class="device-info-item">Выберите устройство из списка</div>';
            document.getElementById('sensors-cards').innerHTML = '';
            showEmptyChart("Выберите устройство для отображения графика");
            return;
        }
        
        try {
            const device = await (await fetch(`/api/device/${selectedDeviceId}`)).json();
            if (!device) return;

            if (currentView === 'dashboard') renderDashboard(device);
            else if (currentView === 'json') renderJsonView(device);
        } catch (error) {
            console.error('Error fetching device details:', error);
        }
    }

    function renderDashboard(device) {
        if (!device) {
            console.error("Не передано устройство для отображения на панели");
            return;
        }
        renderDeviceInfo(device);
        renderSensors(device);
        updateChart(device);
    }

    function renderDeviceInfo(device) {
        const formatUptime = (ms) => {
            if (ms === null || ms === undefined) return 'N/A';
            let s = Math.floor(ms / 1000), m = Math.floor(s / 60), h = Math.floor(m / 60), d = Math.floor(h / 24);
            return `${d}d ${h % 24}h ${m % 60}m ${s % 60}s`;
        };
        
        // Форматирование координат с максимум 6 знаками после запятой
        const formatCoordinate = (coord) => {
            if (coord === null || coord === undefined) return 'N/A';
            return Number(coord).toFixed(6);
        };
        
        // Формируем статус как обычный текст
        const statusText = device.alarm_active
            ? `Alarm (Threshold: ${device.alarm_threshold_c}°C)`
            : `Normal (Threshold: ${device.alarm_threshold_c}°C)`;
        
        // Информация об устройстве в двух столбцах
        const leftColumn = {
            'Status': statusText,
            'Firmware': device.firmware_version || 'N/A',
            'Uptime': formatUptime(device.uptime_ms),
            'Network': device.network || 'N/A',
        };
        
        const rightColumn = {
            'IP Address': device.ip_address || 'N/A',
            'Device ID': device.id,
            'Geo': device.lat !== null ? `${formatCoordinate(device.lat)}, ${formatCoordinate(device.lon)}` : 'N/A'
        };
        
        // Создаем структуру с двумя столбиками
        const panel = document.getElementById('device-info-panel');
        panel.innerHTML = `
            <div class="device-info-columns">
                <div class="device-info-column">
                    ${Object.entries(leftColumn).map(([label, value]) => `
                        <div class="device-info-item">
                            <span class="device-info-label">${label}:</span>
                            <span class="device-info-value">${value}</span>
                        </div>
                    `).join('')}
                </div>
                <div class="device-info-column">
                    ${Object.entries(rightColumn).map(([label, value]) => `
                        <div class="device-info-item">
                            <span class="device-info-label">${label}:</span>
                            <span class="device-info-value">${value}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    function renderSensors(device) {
        const container = document.getElementById('sensors-cards');
        container.innerHTML = '';
        
        // Проверяем, есть ли сенсоры у устройства
        const hasSensors = device.sensors && device.sensors.length > 0;
        
        // Создаем сетку для 4 датчиков
        for (let i = 0; i < 4; i++) {
            const sensor = hasSensors ? device.sensors.find(s => s.sensor_id === i) : null;
            const card = document.createElement('div');
            const headerText = sensor && sensor.name ? sensor.name : `Sensor ${i + 1}`;
            
            if (sensor && sensor.latest_temperature !== null) {
                const temp = sensor.latest_temperature.toFixed(1);
                const isAlarm = device.alarm_active && parseFloat(temp) > device.alarm_threshold_c;
                
                // Форматируем дату и время измерения
                const measurementTime = sensor.last_reading_time ? 
                    new Date(sensor.last_reading_time * 1000).toLocaleString([], {
                        day: '2-digit',
                        month: '2-digit', 
                        year: 'numeric',
                        hour: '2-digit', 
                        minute:'2-digit'
                    }) : 
                    '--.--.---- --:--';
                
                card.className = `sensor-card has-data ${isAlarm ? 'alarm' : ''}`;
                card.innerHTML = `
                    <div class="sensor-header">${headerText}</div>
                    <div class="sensor-temperature">${temp}°C</div>
                    <div class="sensor-humidity">${measurementTime}</div>
                `;
            } else {
                card.className = 'sensor-card inactive';
                card.innerHTML = `
                    <div class="sensor-header">${headerText}</div>
                    <div class="sensor-no-data">No data</div>
                `;
            }
            
            container.appendChild(card);
        }
    }

    function renderJsonView(device) {
        const preEl = document.getElementById('json-pre');
        preEl.textContent = JSON.stringify(JSON.parse(device.raw_json), null, 2);
    }

    async function renderSettingsView() {
        const form = document.getElementById('settings-form');
        const settings = await (await fetch('/api/settings')).json();
        form.elements['server_port'].value = settings.server_port;
        form.elements['ntp_enabled'].checked = settings.ntp_enabled;
        // загрузим max_points
        if (settings.max_points !== undefined) {
            maxPointsSetting = parseInt(settings.max_points, 10) || 1000;
        }
        if (form.elements['max_points']) {
            form.elements['max_points'].value = maxPointsSetting;
        }

        // перехватим submit для сохранения max_points
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const payload = {
                server_port: form.elements['server_port'].value,
                ntp_enabled: form.elements['ntp_enabled'].checked,
                max_points: parseInt(form.elements['max_points'].value || '1000', 10)
            };
            try {
                const resp = await fetch('/api/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
                const data = await resp.json();
                console.log('Settings saved:', data);
                maxPointsSetting = payload.max_points;
                // Если открыт график — перегружаем для применения лимита
                if (selectedDeviceId && currentView === 'dashboard') {
                    const device = await (await fetch(`/api/device/${selectedDeviceId}`)).json();
                    if (device) updateChart(device);
                }
            } catch (err) {
                console.error('Failed to save settings', err);
            }
        }, { once: true });
    }

    async function updateChart(device) {
        if (!device) {
            console.error("Не передано устройство для обновления графика");
            showEmptyChart("Выберите устройство для отображения графика");
            return;
        }
    const loadingEl = document.getElementById('chart-loading');
    if (loadingEl) loadingEl.style.display = 'inline-block';
        
    // Всегда пересоздаем график для надежного применения настроек периода
    if (temperatureChart) { temperatureChart.destroy(); temperatureChart = null; }

    const colors = ['#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#909399'];
        const datasets = [];
    const hiddenSet = getHiddenSet(device.id);
        
        // Рассчитываем временные границы для запроса
        const now = Math.floor(Date.now() / 1000); // Текущее время в секундах
        let endTime, startTime;
        let isAllTime = (selectedPeriod === 'all');
        
        if (!isAllTime) {
            // Привязываем все отрезки к последнему времени данных устройства (как для 1 часа)
            const latestFromSensors = (device?.sensors?.length)
                ? Math.max(...device.sensors.map(s => (s.last_reading_time ? s.last_reading_time : 0)))
                : 0;
            const latestBase = latestFromSensors > 0 ? latestFromSensors : now;
            endTime = timeOffset === 0 ? latestBase : (latestBase - (timeOffset * 3600));
            startTime = endTime - (selectedPeriod * 3600);
        } else {
            // для всего времени запрашиваем от 0 до текущего момента
            startTime = 0;
            endTime = now;
        }

        // Страховка от инверсии диапазона
        if (startTime > endTime) {
            const tmp = startTime; startTime = endTime; endTime = tmp;
        }
        
        console.log(`Период графика: ${selectedPeriod} часов, смещение: ${timeOffset} часов`);
        console.log(`Запрос данных за период: ${new Date(startTime*1000).toLocaleString()} - ${new Date(endTime*1000).toLocaleString()}`);
        
        // Обновляем заголовок графика с информацией о временном диапазоне
    // Заголовок обновим ниже после возможного пересчета диапазона
        
        // deterministic order by sensor_id
        const sensorsOrdered = (device.sensors || []).slice().sort((a,b)=> (a.sensor_id ?? 0) - (b.sensor_id ?? 0));
        for (let i = 0; i < sensorsOrdered.length; i++) {
            const sensor = sensorsOrdered[i];
            const body = { device_id: device.id, sensor_id: sensor.sensor_id, start_time: startTime, end_time: endTime, max_points: maxPointsSetting };
            const history = await (await fetch('/api/history', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            })).json();
            let series = history.map(p => ({ x: p.timestamp * 1000, y: p.temperature_c }));
            datasets.push({
                label: sensor.name || `Sensor ${sensor.sensor_id}`,
                data: series,
                borderColor: colors[i % colors.length], tension: 0.1, fill: false,
                // Track sensor id for persistence and apply hidden state
                _sensorId: sensor.sensor_id,
                hidden: hiddenSet.has(String(sensor.sensor_id))
            });
            console.log(`Получено ${history.length} точек данных для сенсора ${sensor.sensor_id}`);
        }

        // Если выбран режим "всё время", определяем реальные границы по данным
        if (isAllTime) {
            const allPoints = datasets.flatMap(ds => ds.data);
            if (allPoints.length > 0) {
                startTime = Math.floor(Math.min(...allPoints.map(p => p.x)) / 1000);
                endTime = Math.floor(Math.max(...allPoints.map(p => p.x)) / 1000);
            } else {
                // fallback: если данных нет
                startTime = now - 3600; endTime = now;
            }
        }

        // Обновляем заголовок графика с информацией о временном диапазоне
    updateChartTitle(startTime, endTime);
    // Вместо текста периода показываем даты начала/конца данных у устройства
    (async () => {
        try {
            const resp = await fetch(`/api/device_range/${device.id}`);
            const range = await resp.json();
            const sEl = document.getElementById('infoStartDate');
            const eEl = document.getElementById('infoEndDate');
            const fmt = (sec) => sec==null? '--.--.----' : new Date(sec*1000).toLocaleDateString('ru-RU');
            if (sEl) sEl.textContent = fmt(range.min);
            if (eEl) eEl.textContent = fmt(range.max);
        } catch (_) { /* ignore */ }
    })();

        // Сохраняем реальное последнее время показаний по устройству (из sensors)
        try {
            const latestFromSensors = Math.max(
                ...device.sensors
                    .map(s => (s.last_reading_time ? s.last_reading_time * 1000 : -Infinity))
            );
            if (!Number.isNaN(latestFromSensors) && latestFromSensors !== -Infinity) {
                if (!temperatureChart) {
                    // временно положим на объект функции, позже перенесем на инстанс графика
                } else {
                    temperatureChart.globalLatestTime = latestFromSensors;
                }
            }
        } catch (e) { /* ignore */ }
        
        // Если данных нет ни для одного сенсора, показываем заглушку
        const totalDataPoints = datasets.reduce((sum, dataset) => sum + dataset.data.length, 0);
        if (totalDataPoints === 0) {
            showEmptyChart("Ожидание данных...\nДанные появятся после получения показаний от устройства");
            return;
        }
        
    if (!temperatureChart) {
            temperatureChart = new Chart(chartCanvas, {
                type: 'line', 
                data: { datasets },
                options: { 
                    responsive: true, 
                    maintainAspectRatio: false, 
                    animation: false,
                    interaction: {
                        intersect: false,
                        mode: 'index'
                    },
                    onClick: (event, elements) => {
                        // Обработчик клика по графику: позиционируем ползунок по времени шкалы
                        const canvasPosition = Chart.helpers.getRelativePosition(event, temperatureChart);
                        const xScale = temperatureChart.scales.x;
                        const dataX = xScale.getValueForPixel(canvasPosition.x);
                        
                        if (dataX) {
                            // Собираем все точки
                            let allDataPoints = [];
                            datasets.forEach(dataset => {
                                dataset.data.forEach(point => {
                                    allDataPoints.push({
                                        time: point.x,
                                        temperature: point.y,
                                        sensorName: dataset.label
                                    });
                                });
                            });
                            allDataPoints.sort((a, b) => a.time - b.time);

                            // Значение ползунка как доля времени видимого диапазона
                            const tMin = xScale.min, tMax = xScale.max;
                            const clamped = Math.max(tMin, Math.min(tMax, dataX));
                            const progress = (clamped - tMin) / (tMax - tMin);
                            document.getElementById('timeSlider').value = Math.round(progress * 100);

                            // Находим ближайшие показания к времени клика для отображения
                            const closestPoint = allDataPoints.reduce((prev, curr) => 
                                Math.abs(curr.time - dataX) < Math.abs(prev.time - dataX) ? curr : prev
                            );

                            const date = new Date(clamped);
                            const timeString = date.toLocaleString('ru-RU', {
                                day: '2-digit', month: '2-digit', year: 'numeric',
                                hour: '2-digit', minute: '2-digit', hour12: false
                            });
                            document.getElementById('sliderTime').textContent = timeString;
                            document.getElementById('sliderTemperature').textContent = `${closestPoint.temperature.toFixed(1)}°C (${closestPoint.sensorName})`;

                            updateSensorCardsWithSliderData(clamped, allDataPoints);
                            updateChartCrosshair(clamped, closestPoint.temperature, allDataPoints);
                            // Подсветка, если не на последнем времени
                            if (typeof updateHighlightForTime === 'function') {
                                updateHighlightForTime(clamped);
                            }
                        }
                    },
                    scales: { 
                        x: { 
                            type: 'time', 
                            time: { 
                                unit: (isAllTime ? 'day' : (selectedPeriod <= 3 ? 'minute' : 'hour')), 
                                tooltipFormat: 'HH:mm:ss',
                                displayFormats: {
                                    minute: 'HH:mm',
                                    hour: 'HH:mm',
                                    day: 'dd.MM'
                                }
                            },
                            min: startTime * 1000,
                            max: endTime * 1000,
                            ticks: {
                                maxRotation: 0,
                                display: true // Убедимся, что метки видны
                            }
                        }, 
                        y: { 
                            title: { display: true, text: 'Temperature (°C)' },
                            beginAtZero: false,
                            ticks: {
                                display: true // Убедимся, что метки видны
                            }
                        } 
                    },
                    plugins: {
                        legend: {
                            position: 'top',
                            // Persist visibility toggles across rebuilds
                            onClick: (e, legendItem, legend) => {
                                const chart = legend.chart;
                                const index = legendItem.datasetIndex;
                                const visible = chart.isDatasetVisible(index);
                                // Toggle visibility
                                chart.setDatasetVisibility(index, !visible);
                                chart.update();
                                // Persist hidden set
                try {
                                    const ds = chart.data.datasets[index];
                                    const sensorId = ds && ds._sensorId;
                                    if (sensorId !== undefined) {
                    const hs = getHiddenSet(device.id);
                    const key = String(sensorId);
                    if (visible) { hs.add(key); } else { hs.delete(key); }
                                        saveHiddenSet(device.id, hs);
                                    }
                                } catch (_) { /* ignore persistence errors */ }
                            }
                        },
                        tooltip: {
                            enabled: false
                        }
                    }
                },
                plugins: [{
                    id: 'crosshair',
                    afterDraw: (chart) => {
                        const ctx = chart.ctx;
                        const chartArea = chart.chartArea;
                        const xScale = chart.scales.x;
                        if (!xScale || !chartArea) return;

                        // Тонкие серые пунктирные линии начала суток (локальное время)
                        try {
                            const tMin = xScale.min;
                            const tMax = xScale.max;
                            if (isFinite(tMin) && isFinite(tMax) && tMax > tMin) {
                                let d = new Date(tMin);
                                d.setHours(0, 0, 0, 0);
                                let midnight = d.getTime();
                                if (midnight < tMin) midnight += 24 * 60 * 60 * 1000; // следующая полночь, если уже прошла

                                ctx.save();
                                ctx.strokeStyle = '#cfd8dc'; // светло-серый
                                ctx.lineWidth = 1;
                                ctx.setLineDash([3, 3]);
                                for (let ms = midnight; ms <= tMax; ms += 24 * 60 * 60 * 1000) {
                                    const x = xScale.getPixelForValue(ms);
                                    if (x >= chartArea.left && x <= chartArea.right) {
                                        ctx.beginPath();
                                        ctx.moveTo(x, chartArea.top);
                                        ctx.lineTo(x, chartArea.bottom);
                                        ctx.stroke();
                                    }
                                }
                                ctx.restore();
                            }
                        } catch (e) { /* ignore day-lines errors */ }

                        // Дальше рисуем красную линию и треугольник, если задано время курсора
                        if (!chart.crosshairTime) return;
                        const time = chart.crosshairTime;
                        const allDataPoints = chart.crosshairData;

                        // Позиция по времени
                        const xPos = xScale.getPixelForValue(time);
                        if (xPos < chartArea.left || xPos > chartArea.right) return;

                        ctx.save();
                        // Настройки красной пунктирной линии
                        ctx.strokeStyle = '#ff0000';
                        ctx.lineWidth = 1.7; // тоньше в ~3 раза
                        ctx.setLineDash([5, 5]);

                        // Треугольник рисуем на самом канвасе, ориентируясь на зону оси X
                        const axisPadding = xScale.bottom - chartArea.bottom; // пространство оси
                        const tipOffset = Math.min(12, Math.max(6, axisPadding - 2));
                        const tipY = chartArea.bottom + tipOffset; // вершина треугольника (вниз)
                        const triHeight = 12; // px
                        const baseY = tipY - triHeight;
                        const triHalfWidth = 8;

                        // Центроид треугольника
                        const centroidY = (tipY + 2 * baseY) / 3;

                        // Вертикальная пунктирная линия от центроида вверх до верха графика
                        ctx.beginPath();
                        ctx.moveTo(xPos, centroidY);
                        ctx.lineTo(xPos, chartArea.top);
                        ctx.stroke();

                        // Сам треугольник
                        ctx.setLineDash([]);
                        ctx.fillStyle = '#ff0000';
                        ctx.beginPath();
                        ctx.moveTo(xPos, tipY);
                        ctx.lineTo(xPos - triHalfWidth, baseY);
                        ctx.lineTo(xPos + triHalfWidth, baseY);
                        ctx.closePath();
                        ctx.fill();

                        // Убраны подписи температур рядом с линией по просьбе пользователя
                        ctx.restore();
                    }
                }]
            });

            // Enforce persisted hidden state after chart creation
            try {
                const persistedHidden = getHiddenSet(device.id);
                temperatureChart.data.datasets.forEach((ds, idx) => {
                    const shouldHide = persistedHidden.has(String(ds._sensorId));
                    if (shouldHide) {
                        temperatureChart.setDatasetVisibility(idx, false);
                        const meta = temperatureChart.getDatasetMeta(idx);
                        if (meta) meta.hidden = true;
                    }
                });
                temperatureChart.update('none');
            } catch (e) { /* ignore */ }

            // Управление красной линией перетаскиванием по канвасу
            let isDragging = false;
            const setCardsHighlight = (on) => {
                const cards = document.querySelectorAll('#sensors-cards .sensor-card');
                cards.forEach(c => c.classList.toggle('highlight', !!on));
            };
            const getLatestTimeFromDatasets = () => {
                if (!temperatureChart || !temperatureChart.data) return NaN;
                let maxT = -Infinity;
                temperatureChart.data.datasets.forEach(ds => {
                    ds.data.forEach(p => { if (p.x > maxT) maxT = p.x; });
                });
                return maxT;
            };
            const updateHighlightForTime = (t) => {
                const latest = getLatestTimeFromDatasets();
                if (!isFinite(latest)) { setCardsHighlight(false); return; }
                // если курсор не на последнем времени, подсветка включена
                const on = Math.abs(t - latest) > 1000; // >1s от последней точки
                setCardsHighlight(on);
            };
            const getTimeFromEvent = (evt) => {
                const pos = Chart.helpers.getRelativePosition(evt, temperatureChart);
                const xScale = temperatureChart.scales.x;
                const t = xScale.getValueForPixel(pos.x);
                const min = xScale.min, max = xScale.max;
                return Math.min(max, Math.max(min, t));
            };
            const updateFromTime = (t) => {
                // Сбор данных
                const datasetsLocal = temperatureChart.data.datasets;
                let allDataPoints = [];
                datasetsLocal.forEach(dataset => {
                    dataset.data.forEach(point => allDataPoints.push({ time: point.x, temperature: point.y, sensorName: dataset.label }));
                });
                allDataPoints.sort((a,b)=>a.time-b.time);
                const closest = allDataPoints.reduce((p,c)=>Math.abs(c.time-t)<Math.abs(p.time-t)?c:p, allDataPoints[0]);
                // Обновить скрытые поля
                const date = new Date(t);
                const timeString = date.toLocaleString('ru-RU', { day:'2-digit', month:'2-digit', year:'numeric', hour:'2-digit', minute:'2-digit', hour12:false });
                document.getElementById('sliderTime').textContent = timeString;
                document.getElementById('sliderTemperature').textContent = `${closest.temperature.toFixed(1)}°C (${closest.sensorName})`;
                // Карточки и линия
                updateSensorCardsWithSliderData(t, allDataPoints);
                updateChartCrosshair(t, closest.temperature, allDataPoints);
                // Персистентная подсветка по положению курсора
                updateHighlightForTime(t);
                // Обновить инфо-полосу и мини-шкалу
                const infoCurrentTime = document.getElementById('infoCurrentTime');
                if (infoCurrentTime) infoCurrentTime.textContent = date.toLocaleString('ru-RU', { day:'2-digit', month:'2-digit', hour:'2-digit', minute:'2-digit' });
                const xScale = temperatureChart.scales.x;
                const startMS = xScale.min;
                const endMS = xScale.max;
                const total = endMS - startMS;
                const cursorPct = ((t - startMS) / total) * 100;
                const cursorEl = document.getElementById('timelineCursor');
                if (cursorEl) cursorEl.style.left = `${Math.max(0, Math.min(100, cursorPct))}%`;
            };

            const startDrag = (evt) => {
                isDragging = true;
                if (autoReturnTimer) { clearTimeout(autoReturnTimer); autoReturnTimer = null; }
                updateFromTime(getTimeFromEvent(evt));
            };
            const moveDrag = (evt) => {
                if (!isDragging) return;
                updateFromTime(getTimeFromEvent(evt));
            };
            const endDrag = () => {
                if (!isDragging) return;
                isDragging = false;
                // Запустить авто-возврат
                autoReturnTimer = setTimeout(() => {
                    if (temperatureChart && temperatureChart.data.datasets.length > 0) {
                        const datasetsLocal = temperatureChart.data.datasets;
                        const lastDataset = datasetsLocal.find(d => d.data.length > 0);
                        if (lastDataset) {
                            const lastPoint = lastDataset.data[lastDataset.data.length - 1];
                            let allDataPoints = [];
                            datasetsLocal.forEach(dataset => dataset.data.forEach(point => allDataPoints.push({ time: point.x, temperature: point.y, sensorName: dataset.label })));
                            updateSensorCardsWithSliderData(lastPoint.x, allDataPoints);
                            updateChartCrosshair(lastPoint.x, lastPoint.y, allDataPoints);
                            const date = new Date(lastPoint.x);
                            const timeString = date.toLocaleString('ru-RU', { day:'2-digit', month:'2-digit', year:'numeric', hour:'2-digit', minute:'2-digit', hour12:false });
                            document.getElementById('sliderTime').textContent = timeString;
                            document.getElementById('sliderTemperature').textContent = `${lastPoint.y.toFixed(1)}°C`;
                            updateHighlightForTime(lastPoint.x);
                        }
                    }
                }, 5000);
            };

            // Навешиваем обработчики только один раз
            if (!dragHandlersAttached) {
                chartCanvas.addEventListener('mousedown', startDrag);
                window.addEventListener('mousemove', moveDrag);
                window.addEventListener('mouseup', endDrag);
                chartCanvas.addEventListener('touchstart', (e)=>{ if (e.touches && e.touches[0]) startDrag(e.touches[0]); }, {passive:true});
                window.addEventListener('touchmove', (e)=>{ if (e.touches && e.touches[0]) moveDrag(e.touches[0]); }, {passive:true});
                window.addEventListener('touchend', endDrag, {passive:true});
                dragHandlersAttached = true;
            }
        }
        
        // Включаем ползунок времени когда есть данные
        const timeSlider = document.getElementById('timeSlider');
    if (datasets.length > 0 && datasets.some(d => d.data.length > 0)) {
            timeSlider.disabled = false;
            timeSlider.value = 100; // Устанавливаем на конец
            
            // Инициализируем отображение времени последней точки
            const lastDataset = datasets.find(d => d.data.length > 0);
            if (lastDataset) {
                const lastPoint = lastDataset.data[lastDataset.data.length - 1];
                const date = new Date(lastPoint.x);
                const timeString = date.toLocaleString('ru-RU', {
                    day: '2-digit',
                    month: '2-digit',
                    year: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                    hour12: false
                });
                document.getElementById('sliderTime').textContent = timeString;
                document.getElementById('sliderTemperature').textContent = `${lastPoint.y.toFixed(1)}°C`;
                
                // Собираем все данные для инициализации красной линии
                let allDataPoints = [];
                datasets.forEach(dataset => {
                    dataset.data.forEach(point => {
                        allDataPoints.push({
                            time: point.x,
                            temperature: point.y,
                            sensorName: dataset.label
                        });
                    });
                });
                
                // Показываем красную линию на последней точке
                updateChartCrosshair(lastPoint.x, lastPoint.y, allDataPoints);

                // Уточняем глобальное "последнее" время и запоминаем на графике
                try {
                    const latestFromSensors = Math.max(
                        ...device.sensors
                            .map(s => (s.last_reading_time ? s.last_reading_time * 1000 : -Infinity))
                    );
                    if (!Number.isNaN(latestFromSensors) && latestFromSensors !== -Infinity) {
                        temperatureChart.globalLatestTime = latestFromSensors;
                    } else {
                        // если нет данных о last_reading_time — берем максимум из точек на графике
                        const maxFromData = Math.max(...allDataPoints.map(p => p.time));
                        temperatureChart.globalLatestTime = maxFromData;
                    }
                } catch (e) { /* ignore */ }

                // Применяем подсветку в зависимости от положения курсора
                const cards = document.querySelectorAll('#sensors-cards .sensor-card');
                const on = Math.abs(lastPoint.x - (temperatureChart.globalLatestTime || lastPoint.x)) > 1000;
                cards.forEach(c => c.classList.toggle('highlight', on));

                // Обновляем мини-шкалу: прямоугольник = видимый диапазон относительно глобального диапазона устройства
        (async () => {
                    try {
                        const timelineBar = document.querySelector('.timeline-bar');
                        const dataEl = document.getElementById('timelineData');
                        const windowEl = document.getElementById('timelineWindow');
                        const cursorEl = document.getElementById('timelineCursor');
                        if (!(timelineBar && dataEl && windowEl && cursorEl)) return;
                        // Запросим глобальные границы устройства (секунды)
                        const resp = await fetch(`/api/device_range/${device.id}`);
                        const range = await resp.json();
            // Вставим даты по краям
            const sEl = document.getElementById('infoStartDate');
            const eEl = document.getElementById('infoEndDate');
            const fmt = (sec) => sec==null? '--.--.----' : new Date(sec*1000).toLocaleDateString('ru-RU');
            if (sEl) sEl.textContent = fmt(range.min);
            if (eEl) eEl.textContent = fmt(range.max);
                        const gMin = (range && range.min != null) ? range.min * 1000 : NaN;
                        const gMax = (range && range.max != null) ? range.max * 1000 : NaN;
                        if (!isFinite(gMin) || !isFinite(gMax) || gMax <= gMin) {
                            dataEl.style.width = '0%';
                            windowEl.style.width = '0%';
                            cursorEl.style.left = '0%';
                            return;
                        }
                        // Заполняем зону наличия данных (весь доступный диапазон устройства)
                        dataEl.style.left = '0%';
                        dataEl.style.width = '100%';
                        const total = gMax - gMin;
                        const winStart = startTime * 1000;
                        const winEnd = endTime * 1000;
                        const winLeftPct = ((winStart - gMin) / total) * 100;
                        const winWidthPct = Math.max(1, Math.min(100, ((winEnd - winStart) / total) * 100));
                        windowEl.style.left = `${Math.max(0, Math.min(100, winLeftPct))}%`;
                        windowEl.style.width = `${winWidthPct}%`;
                        const cursorPct = ((lastPoint.x - gMin) / total) * 100;
                        cursorEl.style.left = `${Math.max(0, Math.min(100, cursorPct))}%`;
                    } catch (e) {
                        // ignore
                    }
                })();
            }
        } else {
            timeSlider.disabled = true;
            document.getElementById('sliderTime').textContent = '--';
            document.getElementById('sliderTemperature').textContent = '--°C';
        }

    if (loadingEl) loadingEl.style.display = 'none';

        // Блокируем кнопки навигации при режиме "всё время"
        const prevBtn = document.getElementById('chart-prev');
        const nextBtn = document.getElementById('chart-next');
        const nowBtn = document.getElementById('chart-now');
        if (isAllTime) {
            prevBtn.setAttribute('disabled', 'disabled');
            nextBtn.setAttribute('disabled', 'disabled');
        } else {
            prevBtn.removeAttribute('disabled');
            nextBtn.removeAttribute('disabled');
        }
    }
    
    function updateChartCrosshair(time, temperature, allDataPoints) {
        if (!temperatureChart) return;
        
        // Сохраняем текущее время для отрисовки
        temperatureChart.crosshairTime = time;
        temperatureChart.crosshairData = allDataPoints;
        
        // Принудительно обновляем график
        temperatureChart.update('none');
    }
    
    function updateSensorCardsWithSliderData(time, allDataPoints) {
        // Находим ближайшие данные для каждого сенсора в указанное время
        const sensorData = {};
        
        // Группируем данные по сенсорам
        allDataPoints.forEach(point => {
            if (!sensorData[point.sensorName]) {
                sensorData[point.sensorName] = [];
            }
            sensorData[point.sensorName].push(point);
        });
        
        // Для каждого сенсора находим ближайшую точку данных
        const sensorsContainer = document.getElementById('sensors-cards');
        const sensorCards = sensorsContainer.querySelectorAll('.sensor-card');
        
        sensorCards.forEach((card, index) => {
            const sensorName = `Sensor ${index + 1}`;
            const tempElement = card.querySelector('.sensor-temperature');
            const timeElement = card.querySelector('.sensor-humidity'); // Используем для времени
            
            if (sensorData[sensorName] && sensorData[sensorName].length > 0) {
                // Находим ближайшую точку данных для этого сенсора
                const closestPoint = sensorData[sensorName].reduce((prev, curr) => 
                    Math.abs(curr.time - time) < Math.abs(prev.time - time) ? curr : prev
                );
                
                // Обновляем температуру
                tempElement.textContent = `${closestPoint.temperature.toFixed(1)}°C`;
                
                // Обновляем время
                const date = new Date(closestPoint.time);
                const timeString = date.toLocaleString('ru-RU', {
                    day: '2-digit',
                    month: '2-digit',
                    year: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                    hour12: false
                });
                timeElement.textContent = timeString;
            }
        });
    }

    function showEmptyChart(message) {
        // Создаем пустой график с сообщением ожидания данных
        const chartContainer = document.querySelector('.chart-container');
        const chartCanvas = document.getElementById('temperatureChart');
        
        // Уничтожаем существующий график, если есть
        if (temperatureChart) {
            temperatureChart.destroy();
            temperatureChart = null;
        }
        
        // Обновляем заголовок графика
        const chartTitle = document.querySelector('.chart-title');
        if (chartTitle) {
            chartTitle.textContent = 'График температур';
        }
        
        // Создаем новый график без данных, но с правильными размерами
        temperatureChart = new Chart(chartCanvas, {
            type: 'line',
            data: { datasets: [] },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'minute',
                            tooltipFormat: 'HH:mm:ss'
                        },
                        ticks: {
                            display: false
                        },
                        grid: {
                            display: false
                        }
                    },
                    y: {
                        ticks: {
                            display: false
                        },
                        grid: {
                            display: false
                        }
                    }
                },
                plugins: {
                    emptyChartMessage: true, // Добавляем флаг для идентификации
                    legend: {
                        display: false
                    },
                    tooltip: {
                        enabled: false
                    }
                }
            },
            plugins: [{
                id: 'emptyChartMessage',
                afterDraw: function(chart) {
                    if (chart.data.datasets.length === 0) {
                        // Получаем контекст канваса
                        const ctx = chart.ctx;
                        const width = chart.width;
                        const height = chart.height;
                        
                        ctx.save();
                        ctx.textAlign = 'center';
                        ctx.textBaseline = 'middle';
                        ctx.font = '14px Arial';
                        ctx.fillStyle = '#666';
                        
                        // Отображаем текст по центру
                        const lines = message.split('\n');
                        const lineHeight = 20;
                        const startY = height / 2 - (lines.length - 1) * lineHeight / 2;
                        
                        lines.forEach((line, index) => {
                            ctx.fillText(
                                line,
                                width / 2,
                                startY + index * lineHeight
                            );
                        });
                        
                        ctx.restore();
                    }
                }
            }]
        });
        
        // Отключаем ползунок времени для пустого графика
        const timeSlider = document.getElementById('timeSlider');
        timeSlider.disabled = true;
        document.getElementById('sliderTime').textContent = '--';
        document.getElementById('sliderTemperature').textContent = '--°C';
    }
    
    function updateChartTitle(startTime, endTime) {
        const formatTime = (timestamp) => {
            const date = new Date(timestamp * 1000);
            return date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) + 
                   (date.getDate() !== new Date().getDate() ? ' ' + date.toLocaleDateString() : '');
        };
        
        const chartTitle = document.querySelector('.chart-title');
        if (chartTitle) {
            const safeStart = isFinite(startTime) ? startTime : Math.floor(Date.now()/1000) - 3600;
            const safeEnd = isFinite(endTime) ? endTime : Math.floor(Date.now()/1000);
            chartTitle.textContent = `График температур (${formatTime(safeStart)} - ${formatTime(safeEnd)})`;
        }
    }
    
// --- Init ---
    navButtons.forEach(b => b.addEventListener('click', () => showView(b.dataset.view)));
    
    // Обработчики кнопок периода графика
    document.querySelectorAll('.chart-button').forEach(button => {
        button.addEventListener('click', async () => {
            document.querySelectorAll('.chart-button').forEach(b => b.classList.remove('active'));
            button.classList.add('active');
            selectedPeriod = (button.dataset.period === 'all') ? 'all' : parseInt(button.dataset.period, 10);
            console.log(`Выбран период: ${selectedPeriod} часов`);
            timeOffset = 0; // Сбрасываем смещение при смене периода
            if (selectedDeviceId) {
                try {
                    const device = await (await fetch(`/api/device/${selectedDeviceId}`)).json();
                    if (device) updateChart(device);
                } catch (error) {
                    console.error('Error fetching device details:', error);
                }
            }
        });
    });

    // removed approx toggle button and logic
    
    // Обработчики навигации по времени
    document.getElementById('chart-prev').addEventListener('click', async () => {
        if (selectedPeriod === 'all') return; // нет смещения в режиме всё время
        timeOffset += selectedPeriod;
        console.log(`Смещение назад на ${selectedPeriod} часов. Новое смещение: ${timeOffset}`);
        if (selectedDeviceId) {
            try {
                // Получаем свежие данные устройства для обновления графика
                const device = await (await fetch(`/api/device/${selectedDeviceId}`)).json();
                if (device) updateChart(device);
            } catch (error) {
                console.error('Error fetching device details:', error);
            }
        }
    });
    
    document.getElementById('chart-next').addEventListener('click', async () => {
        if (selectedPeriod === 'all') return; // нет смещения в режиме всё время
        timeOffset -= selectedPeriod;
        console.log(`Смещение вперед на ${selectedPeriod} часов. Новое смещение: ${timeOffset}`);
        if (selectedDeviceId) {
            try {
                // Получаем свежие данные устройства для обновления графика
                const device = await (await fetch(`/api/device/${selectedDeviceId}`)).json();
                if (device) updateChart(device);
            } catch (error) {
                console.error('Error fetching device details:', error);
            }
        }
    });

    // Кнопка «сейчас»: сбрасывает смещение и перерисовывает окно
    document.getElementById('chart-now').addEventListener('click', async () => {
        if (selectedPeriod === 'all') return; // в режиме все время окно равно данным
        timeOffset = 0;
        if (selectedDeviceId) {
            try {
                const device = await (await fetch(`/api/device/${selectedDeviceId}`)).json();
                if (device) updateChart(device);
            } catch (error) {
                console.error('Error fetching device details:', error);
            }
        }
    });

    // Обработчик ползунка времени
    const timeSlider = document.getElementById('timeSlider');
    const sliderTime = document.getElementById('sliderTime');
    const sliderTemperature = document.getElementById('sliderTemperature');
    
    let autoReturnTimer = null;
    let isUserInteracting = false;
    
    // Обработчик начала взаимодействия
    timeSlider.addEventListener('mousedown', function() {
        isUserInteracting = true;
        if (autoReturnTimer) {
            clearTimeout(autoReturnTimer);
            autoReturnTimer = null;
        }
    });
    
    // Обработчик конца взаимодействия
    timeSlider.addEventListener('mouseup', function() {
        isUserInteracting = false;
        // Запускаем таймер на 5 секунд
        autoReturnTimer = setTimeout(() => {
            if (!isUserInteracting && temperatureChart && temperatureChart.data.datasets.length > 0) {
                // Возвращаем к последним данным
                timeSlider.value = 100;
                
                // Находим последнюю точку данных
                const datasets = temperatureChart.data.datasets;
                const lastDataset = datasets.find(d => d.data.length > 0);
                if (lastDataset) {
                    const lastPoint = lastDataset.data[lastDataset.data.length - 1];
                    
                    // Собираем все данные
                    let allDataPoints = [];
                    datasets.forEach(dataset => {
                        dataset.data.forEach(point => {
                            allDataPoints.push({
                                time: point.x,
                                temperature: point.y,
                                sensorName: dataset.label
                            });
                        });
                    });
                    
                    // Обновляем карточки и график
                    updateSensorCardsWithSliderData(lastPoint.x, allDataPoints);
                    updateChartCrosshair(lastPoint.x, lastPoint.y, allDataPoints);
                    
                    // Обновляем скрытые элементы
                    const date = new Date(lastPoint.x);
                    const timeString = date.toLocaleString('ru-RU', {
                        day: '2-digit',
                        month: '2-digit',
                        year: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                        hour12: false
                    });
                    document.getElementById('sliderTime').textContent = timeString;
                    document.getElementById('sliderTemperature').textContent = `${lastPoint.y.toFixed(1)}°C`;
                }
            }
        }, 5000);
    });
    
    // Обработчики для сенсорных устройств
    timeSlider.addEventListener('touchstart', function() {
        isUserInteracting = true;
        if (autoReturnTimer) {
            clearTimeout(autoReturnTimer);
            autoReturnTimer = null;
        }
    });
    
    timeSlider.addEventListener('touchend', function() {
        isUserInteracting = false;
        // Запускаем таймер на 5 секунд (тот же код что и для mouseup)
        autoReturnTimer = setTimeout(() => {
            if (!isUserInteracting && temperatureChart && temperatureChart.data.datasets.length > 0) {
                timeSlider.value = 100;
                
                const datasets = temperatureChart.data.datasets;
                const lastDataset = datasets.find(d => d.data.length > 0);
                if (lastDataset) {
                    const lastPoint = lastDataset.data[lastDataset.data.length - 1];
                    
                    let allDataPoints = [];
                    datasets.forEach(dataset => {
                        dataset.data.forEach(point => {
                            allDataPoints.push({
                                time: point.x,
                                temperature: point.y,
                                sensorName: dataset.label
                            });
                        });
                    });
                    
                    updateSensorCardsWithSliderData(lastPoint.x, allDataPoints);
                    updateChartCrosshair(lastPoint.x, lastPoint.y, allDataPoints);
                    
                    const date = new Date(lastPoint.x);
                    const timeString = date.toLocaleString('ru-RU', {
                        day: '2-digit',
                        month: '2-digit',
                        year: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                        hour12: false
                    });
                    document.getElementById('sliderTime').textContent = timeString;
                    document.getElementById('sliderTemperature').textContent = `${lastPoint.y.toFixed(1)}°C`;
                }
            }
        }, 5000);
    });
    
    timeSlider.addEventListener('input', function() {
        if (!temperatureChart || !temperatureChart.data.datasets.length) return;
        
        // Сбрасываем таймер при ручном перемещении
        if (autoReturnTimer) {
            clearTimeout(autoReturnTimer);
            autoReturnTimer = null;
        }
        
        const sliderValue = parseInt(this.value);
        const datasets = temperatureChart.data.datasets;
        const xScale = temperatureChart.scales.x;
        const tMin = xScale.min, tMax = xScale.max;
        const clampedProgress = Math.max(0, Math.min(1, sliderValue / 100));
        const selectedTime = tMin + clampedProgress * (tMax - tMin);
        
        // Собираем все точки данных из всех датчиков
        let allDataPoints = [];
        datasets.forEach(dataset => {
            dataset.data.forEach(point => {
                allDataPoints.push({
                    time: point.x,
                    temperature: point.y,
                    sensorName: dataset.label
                });
            });
        });
        
        // Сортируем по времени
        allDataPoints.sort((a, b) => a.time - b.time);
        
        if (allDataPoints.length === 0) return;
        
        // Находим ближайшую точку для отображения температуры
        const closestPoint = allDataPoints.reduce((prev, curr) => 
            Math.abs(curr.time - selectedTime) < Math.abs(prev.time - selectedTime) ? curr : prev
        );
        
        // Обновляем скрытые элементы времени и температуры
        const date = new Date(selectedTime);
        const timeString = date.toLocaleString('ru-RU', {
            day: '2-digit', month: '2-digit', year: 'numeric',
            hour: '2-digit', minute: '2-digit', hour12: false
        });
        document.getElementById('sliderTime').textContent = timeString;
        document.getElementById('sliderTemperature').textContent = `${closestPoint.temperature.toFixed(1)}°C (${closestPoint.sensorName})`;
        
        // Обновляем карточки сенсоров с данными в выбранное время
        updateSensorCardsWithSliderData(selectedTime, allDataPoints);
        
        // Красная линия строго по выбранному времени
        updateChartCrosshair(selectedTime, closestPoint.temperature, allDataPoints);
        // Подсветка карточек в зависимости от положения
        if (typeof updateHighlightForTime === 'function') {
            updateHighlightForTime(selectedTime);
        }
    });
    
    // Первоначальная загрузка списка устройств
    fetchDevicesList();

    // О программе: модальное окно
    const aboutBtn = document.getElementById('about-btn');
    const aboutModal = document.getElementById('about-modal');
    const aboutClose = document.getElementById('about-close');
    const aboutContent = document.getElementById('about-content');
    const openAbout = async () => {
        try {
            const s = await (await fetch('/api/settings')).json();
            aboutContent.innerHTML = `
                <div><strong>Версия:</strong> ${s.app_version || '—'}</div>
                <div><strong>Разработчик:</strong> ${s.developer || 'Serbinov Oleg'}</div>
                ${s.repo_url ? `<div><strong>Репозиторий:</strong> <a href="${s.repo_url}" target="_blank" rel="noopener">${s.repo_url}</a></div>` : ''}
                ${s.json_protocol_url ? `<div><strong>ThermoGrid Telemetry JSON Protocol (TG-TJP v1.0):</strong> <a href="${s.json_protocol_url}" target="_blank" rel="noopener">${s.json_protocol_url}</a></div>` : ''}
            `;
        } catch (e) {
            aboutContent.textContent = 'Ошибка загрузки информации.';
        }
        aboutModal.style.display = 'flex';
    };
    if (aboutBtn && aboutModal && aboutClose) {
        aboutBtn.addEventListener('click', openAbout);
        aboutClose.addEventListener('click', () => aboutModal.style.display = 'none');
        aboutModal.addEventListener('click', (e) => { if (e.target === aboutModal) aboutModal.style.display = 'none'; });
    }
});

