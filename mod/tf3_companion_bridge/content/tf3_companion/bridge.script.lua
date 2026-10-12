-- TF3 Companion Bridge
--
-- Runs on the GUI thread (guiUpdate) and periodically writes a read-only snapshot
-- of the player's company as towns_industries/tf3c_snap_<gameTime>.lua.
-- It never sends commands, so the simulation is untouched.
--
-- A snapshot is written when:
--   * no snapshot was written yet in this session/save (or the game time went backwards),
--   * 1/SNAPSHOTS_PER_YEAR of a game year has passed since the last one,
--   * the external tool wrote a request file with a new `id`.
--
-- Every collector runs under pcall; failures are reported in snapshot.errors
-- instead of aborting the whole snapshot.

local bridge = {}

local SCHEMA_VERSION = 1
local MOD_REVISION = 1
local DIR = "towns_industries"
local REQUEST_FILE = "tf3c_request"
local SNAPSHOTS_PER_YEAR = 12
local REQUEST_POLL_FRAMES = 60
local MAX_ERRORS = 100

local CARRIERS = { "ROAD", "RAIL", "TRAM", "WATER", "AIR", "OTHER" }
local VEHICLE_STATES = { "IN_DEPOT", "EN_ROUTE", "AT_TERMINAL", "GOING_TO_DEPOT" }
local LOAD_MODES = { "LOAD_IF_AVAILABLE", "FULL_LOAD_ANY", "FULL_LOAD_ALL", "LEGACY_UNLOAD_ONLY" }
local LINE_ISSUES = { "NowhereToLoad", "NowhereToUnload", "NoVehicleToLoadCargo", "VehicleUseless", "LineCargoConfig", "None" }

-- ---------------------------------------------------------------------------
-- helpers

local function log(msg)
	print("[tf3c] " .. msg)
end

local function addError(ctx, label, err)
	if #ctx.errors < MAX_ERRORS then
		ctx.errors[#ctx.errors + 1] = label .. ": " .. tostring(err)
	end
end

--- Calls fn(...) under pcall; on failure records the error and returns nil.
local function try(ctx, label, fn, ...)
	local ok, result = pcall(fn, ...)
	if ok then
		return result
	end
	addError(ctx, label, result)
	return nil
end

--- Copies a Lua array of plain values (entity ids, numbers) into a fresh table.
local function copyArray(list)
	local out = {}
	if list then
		for i = 1, #list do
			out[i] = list[i]
		end
	end
	return out
end

--- Maps an engine enum value to its name. `getEnum` returns the enum table.
local function enumName(getEnum, value, names)
	if value == nil then
		return nil
	end
	local ok, enum = pcall(getEnum)
	if ok and enum then
		for _, name in ipairs(names) do
			local okv, candidate = pcall(function() return enum[name] end)
			if okv and candidate ~= nil and candidate == value then
				return name
			end
		end
	end
	return tostring(value)
end

local function carrierName(value)
	return enumName(function() return api.type.enum.Carrier end, value, CARRIERS)
end

local function vehicleStateName(value)
	return enumName(function() return api.type.enum.TransportVehicleState end, value, VEHICLE_STATES)
end

local function loadModeName(value)
	return enumName(function() return api.engine.Component.Line.LoadMode end, value, LOAD_MODES)
end

local function lineIssueName(value)
	return enumName(function() return api.type.LineIssue.Type end, value, LINE_ISSUES)
end

local function entityName(entity)
	local ok, name = pcall(api.engine.util.getEntityName, entity)
	if ok then
		return name
	end
	return nil
end

local function getComponent(entity, componentType)
	return api.engine.getComponent(entity, componentType)
end

-- ---------------------------------------------------------------------------
-- resource caches (cargo types, vehicle models)

local function cargoRef(ctx, cargoId)
	if cargoId == nil or cargoId < 0 then
		return nil
	end
	if not ctx.cargoSeen[cargoId] then
		ctx.cargoSeen[cargoId] = true
		local entry = { id = cargoId }
		local ok, cargo = pcall(api.res.cargoTypeRep.get, cargoId)
		if ok and cargo then
			entry.name = cargo.name
		end
		local okRes, resName = pcall(api.res.cargoTypeRep.getName, cargoId)
		if okRes then
			entry.res = resName
		end
		ctx.snapshot.cargos[#ctx.snapshot.cargos + 1] = entry
	end
	return cargoId
end

local function modelRef(ctx, modelId)
	if modelId == nil then
		return nil
	end
	if not ctx.modelSeen[modelId] then
		ctx.modelSeen[modelId] = true
		local entry = { id = modelId }
		local okRes, resName = pcall(api.res.modelRep.getName, modelId)
		if okRes then
			entry.res = resName
		end
		local ok, model = pcall(api.res.modelRep.get, modelId)
		if ok and model then
			pcall(function()
				local maintenance = model.metadata.maintenance
				if maintenance then
					entry.lifespan = maintenance.lifespan
					entry.runningCosts = maintenance.runningCosts
				end
			end)
			pcall(function()
				local cost = model.metadata.cost
				if cost then
					entry.price = cost.price
				end
			end)
			pcall(function()
				local description = model.metadata.description
				if description then
					entry.name = description.name
				end
			end)
		end
		ctx.snapshot.models[#ctx.snapshot.models + 1] = entry
	end
	return modelId
end

-- ---------------------------------------------------------------------------
-- collectors

local function collectMeta(ctx, reason, requestId)
	local snapshot = ctx.snapshot
	local meta = {
		schemaVersion = SCHEMA_VERSION,
		modRevision = MOD_REVISION,
		reason = reason,
		requestId = requestId,
		gameTime = ctx.now,
		yearDuration = ctx.yearDuration,
	}
	meta.buildVersion = try(ctx, "meta.buildVersion", getBuildVersion)
	meta.year = try(ctx, "meta.year", api.engine.util.getYear)
	local date = try(ctx, "meta.date", api.engine.util.getCalendarDate, ctx.now)
	if date then
		meta.date = { year = date.year, month = date.month, day = date.day }
	end
	snapshot.meta = meta
end

local function collectCompany(ctx)
	local company = { player = ctx.player }
	local account = try(ctx, "company.account", getComponent, ctx.player, api.type.ComponentType.ACCOUNT)
	if account then
		company.balance = account.balance
		company.loan = account.loan
	end
	company.earnings = try(ctx, "company.earnings", api.engine.util.finance.calculateEarnings, ctx.player)
	local value = try(ctx, "company.value", api.engine.util.headquarters.getCompaniesValue)
	if value then
		company.value = {
			totalScore = value.totalScore,
			railVehicles = value.railVehicles,
			trams = value.trams,
			roadVehicles = value.roadVehicles,
			aircrafts = value.aircrafts,
			ships = value.ships,
			trackTotalLength = value.trackTotalLength,
			trackElectricLength = value.trackElectricLength,
		}
	end
	local transported = try(ctx, "company.transported", api.engine.util.headquarters.getTransportedData)
	if transported then
		company.passengersTransported = transported.passengersTransported
		company.cargoTransported = transported.cargoTransported
	end
	ctx.snapshot.company = company
end

local function collectLine(ctx, lineId)
	local label = "line[" .. tostring(lineId) .. "]"
	local out = { id = lineId, name = entityName(lineId), stops = {} }

	local line = try(ctx, label .. ".component", getComponent, lineId, api.type.ComponentType.LINE)
	if line then
		for i, stop in ipairs(line.stops) do
			out.stops[i] = {
				stationGroup = stop.stationGroup,
				name = entityName(stop.stationGroup),
				station = stop.station,
				terminal = stop.terminal,
				loadMode = loadModeName(stop.loadMode),
				minWaitingTime = stop.minWaitingTime,
				maxWaitingTime = stop.maxWaitingTime,
			}
			ctx.stationGroups[stop.stationGroup] = true
		end
	end

	out.vehicles = copyArray(try(ctx, label .. ".vehicles", api.engine.system.transportVehicleSystem.getLineVehicles, lineId))
	out.profitYear = try(ctx, label .. ".profitYear", api.engine.util.finance.calculateBalance, { lineId }, ctx.fromTime, ctx.now, true)
	out.transportedYear = try(ctx, label .. ".transportedYear", api.engine.util.logbook.getLogValuePerYear, lineId, "itemsTransported")
	out.rate = try(ctx, label .. ".rate", api.engine.util.line.calcLineStationThroughput, lineId)
	out.maxFrequency = try(ctx, label .. ".maxFrequency", api.engine.util.line.getMaxFrequency, lineId)

	local usages = try(ctx, label .. ".capacity", api.engine.util.line.getLineCapacityUsages, lineId, false)
	out.capacity = {}
	if usages then
		for cargoId, usage in pairs(usages) do
			out.capacity[#out.capacity + 1] = {
				cargo = cargoRef(ctx, cargoId),
				used = usage.used,
				capacity = usage.capacity,
			}
		end
	end

	local issues = try(ctx, label .. ".issues", api.engine.util.line.getLineIssues, lineId, false)
	out.issues = {}
	if issues then
		for _, issue in ipairs(issues) do
			out.issues[#out.issues + 1] = {
				type = lineIssueName(issue.type),
				stopIndex = issue.stopIndex,
				cargo = cargoRef(ctx, issue.cargoType),
			}
		end
	end

	return out
end

local function collectLines(ctx)
	local lines = {}
	local ids = try(ctx, "lines.list", api.engine.system.lineSystem.getLinesForPlayer, ctx.player) or {}
	for _, lineId in ipairs(ids) do
		local line = try(ctx, "line[" .. tostring(lineId) .. "]", collectLine, ctx, lineId)
		if line then
			lines[#lines + 1] = line
		end
	end
	ctx.snapshot.lines = lines
end

local function isPlayerOwned(ctx, entity)
	local owned = getComponent(entity, api.type.ComponentType.PLAYER_OWNED)
	return owned ~= nil and owned.player == ctx.player
end

local function collectVehicle(ctx, vehicleId)
	local label = "vehicle[" .. tostring(vehicleId) .. "]"
	local tv = getComponent(vehicleId, api.type.ComponentType.TRANSPORT_VEHICLE)
	if not tv then
		return nil
	end
	local out = {
		id = vehicleId,
		name = entityName(vehicleId),
		carrier = carrierName(tv.carrier),
		state = vehicleStateName(tv.state),
		line = tv.line,
		stopIndex = tv.stopIndex,
		userStopped = tv.userStopped,
		sellOnArrival = tv.sellOnArrival,
		noPath = tv.noPath,
		daysInDepot = tv.daysInDepot,
		daysAtTerminal = tv.daysAtTerminal,
		depot = tv.depot,
		models = {},
	}

	local purchaseTime
	local parts = tv.transportVehicleConfig and tv.transportVehicleConfig.vehicles or {}
	for _, part in ipairs(parts) do
		if part.purchaseTime and (purchaseTime == nil or part.purchaseTime < purchaseTime) then
			purchaseTime = part.purchaseTime
		end
		if part.part then
			out.models[#out.models + 1] = modelRef(ctx, part.part.modelId)
		end
	end
	out.parts = #parts
	out.purchaseTime = purchaseTime

	out.maintenanceState = try(ctx, label .. ".maintenanceState", api.engine.util.vehicle.getVehicleMaintenanceState, vehicleId)
	out.value = try(ctx, label .. ".value", api.engine.util.vehicle.getDepreciatedValue, vehicleId)
	out.runningCost = try(ctx, label .. ".runningCost", api.engine.util.vehicle.getRunningCost, vehicleId)
	out.profitYear = try(ctx, label .. ".profitYear", api.engine.util.finance.calculateBalance, { vehicleId }, ctx.fromTime, ctx.now, true)
	local capacities = try(ctx, label .. ".capacities", api.engine.util.vehicle.getVehicleCapacities, vehicleId)
	if capacities then
		local total = 0
		for _, value in pairs(capacities) do
			total = total + value
		end
		out.capacity = total
	end
	-- cargo the vehicle is configured to carry now, and everything it could carry (index = cargoTypeId + 1)
	out.loadConfig = {}
	out.canCarry = {}
	local config = tv.config
	if config then
		for index, capacity in ipairs(config.capacities or {}) do
			if capacity > 0 then
				out.loadConfig[#out.loadConfig + 1] = { cargo = cargoRef(ctx, index - 1), capacity = capacity }
			end
		end
		for index, capacity in ipairs(config.allCaps or {}) do
			if capacity > 0 then
				out.canCarry[#out.canCarry + 1] = cargoRef(ctx, index - 1)
			end
		end
	end
	if tv.depot and tv.depot >= 0 then
		ctx.depots[tv.depot] = true
	end
	return out
end

local function collectVehicles(ctx)
	local vehicles = {}
	local ids = try(ctx, "vehicles.list", api.engine.util.vehicle.getVehicles) or {}
	for _, vehicleId in ipairs(ids) do
		local owned = try(ctx, "vehicle[" .. tostring(vehicleId) .. "].owner", isPlayerOwned, ctx, vehicleId)
		if owned then
			local vehicle = try(ctx, "vehicle[" .. tostring(vehicleId) .. "]", collectVehicle, ctx, vehicleId)
			if vehicle then
				vehicles[#vehicles + 1] = vehicle
			end
		end
	end
	ctx.snapshot.vehicles = vehicles
end

local function collectStations(ctx)
	local stations = {}
	for groupId in pairs(ctx.stationGroups) do
		local label = "station[" .. tostring(groupId) .. "]"
		local out = { id = groupId, name = entityName(groupId) }
		local group = try(ctx, label .. ".component", getComponent, groupId, api.type.ComponentType.STATION_GROUP)
		if group and group.stations and group.stations[1] then
			out.town = try(ctx, label .. ".town", api.engine.system.stationSystem.getTown, group.stations[1])
			out.townName = out.town and entityName(out.town) or nil
		end
		out.lines = copyArray(try(ctx, label .. ".lines", api.engine.system.lineSystem.getLinesForStationGroup, groupId))
		out.maintenance = try(ctx, label .. ".maintenance", api.engine.util.maintenance.calcMaintenanceForStationGroup, groupId)
		stations[#stations + 1] = out
	end
	ctx.snapshot.stations = stations
end

local function cargoFlows(ctx, label, stockListId, cargoIds, isOutput)
	local flows = {}
	local stock = api.engine.util.stock
	for _, cargoId in ipairs(cargoIds or {}) do
		local flow = { cargo = cargoRef(ctx, cargoId) }
		local cargoLabel = label .. ".cargo[" .. tostring(cargoId) .. "]"
		if isOutput then
			flow.producedYear = try(ctx, cargoLabel .. ".produced", stock.getCargoProducedPerYear, stockListId, cargoId)
			flow.maxProductionYear = try(ctx, cargoLabel .. ".maxProduction", stock.getCargoMaxProductionPerYear, stockListId, cargoId)
			flow.shippedYear = try(ctx, cargoLabel .. ".shipped", stock.getCargoTypeShippedPerYear, stockListId, cargoId)
		else
			flow.consumedYear = try(ctx, cargoLabel .. ".consumed", stock.getCargoConsumedPerYear, stockListId, cargoId)
			flow.maxConsumptionYear = try(ctx, cargoLabel .. ".maxConsumption", stock.getCargoMaxConsumptionPerYear, stockListId, cargoId)
			flow.deliveredYear = try(ctx, cargoLabel .. ".delivered", stock.getCargoTypeDeliveredPerYear, stockListId, cargoId)
		end
		flows[#flows + 1] = flow
	end
	return flows
end

local function constructionInfo(ctx, label, constructionId, out)
	local construction = try(ctx, label .. ".construction", getComponent, constructionId, api.type.ComponentType.CONSTRUCTION)
	if construction then
		out.type = construction.fileName
		pcall(function()
			local transf = construction.transf
			out.position = { transf[13], transf[14], transf[15] }
		end)
	end
end

local function collectIndustries(ctx)
	local industries = {}
	local ids = try(ctx, "industries.list", api.engine.getEntitiesWithComponent, api.type.ComponentType.INDUSTRY) or {}
	for _, industryId in ipairs(ids) do
		local label = "industry[" .. tostring(industryId) .. "]"
		local industry = try(ctx, label .. ".component", getComponent, industryId, api.type.ComponentType.INDUSTRY)
		if industry then
			local out = {
				id = industryId,
				name = entityName(industryId),
				level = industry.level,
				maxLevel = industry.maxLevel,
				closureTimeStamp = industry.closureTimeStamp,
				upgradeProgress = industry.upgradeProgress,
				stockList = industry.stockList,
			}
			constructionInfo(ctx, label, industry.construction, out)
			local stockListId = industry.stockList
			out.productionRating = try(ctx, label .. ".productionRating", api.engine.util.stock.getProductionRating, stockListId)
			local rules = try(ctx, label .. ".rules", api.engine.util.stock.getInputsOutputsFromRules, stockListId)
			if rules then
				out.inputs = cargoFlows(ctx, label, stockListId, rules[1], false)
				out.outputs = cargoFlows(ctx, label, stockListId, rules[2], true)
			end
			industries[#industries + 1] = out
		end
	end
	ctx.snapshot.industries = industries
end

local function collectTowns(ctx)
	local towns = {}
	local ids = try(ctx, "towns.list", api.engine.getEntitiesWithComponent, api.type.ComponentType.TOWN) or {}
	for _, townId in ipairs(ids) do
		local label = "town[" .. tostring(townId) .. "]"
		local town = try(ctx, label .. ".component", getComponent, townId, api.type.ComponentType.TOWN)
		if town then
			local out = {
				id = townId,
				name = entityName(townId),
				developmentActive = town.developmentActive,
				noise = town.noise,
				pollution = town.pollution,
			}
			-- {residential, commercial, industrial} person capacities
			out.capacities = copyArray(try(ctx, label .. ".capacities", api.engine.system.townBuildingSystem.getLandUsePersonCapacities, townId))
			out.lineUsage = try(ctx, label .. ".lineUsage", api.engine.util.town.getTownLineUsage, townId)
			local supply = try(ctx, label .. ".cargoSupply", api.engine.system.townBuildingSystem.getCargoSupplyAndLimit, townId)
			out.cargoSupply = {}
			if supply then
				for cargoId, values in pairs(supply) do
					out.cargoSupply[#out.cargoSupply + 1] = {
						cargo = cargoRef(ctx, cargoId),
						supply = values[1],
						limit = values[2],
						extra = values[3],
					}
				end
			end
			towns[#towns + 1] = out
		end
	end
	ctx.snapshot.towns = towns
end

local function collectProblems(ctx)
	local problems = {}
	problems.noPathVehicles = copyArray(try(ctx, "problems.noPathVehicles", api.engine.system.transportVehicleSystem.getNoPathVehicles))
	local closing = try(ctx, "problems.closingIndustries", api.engine.util.industry.getClosingIndustries)
	problems.closingIndustries = {}
	if closing then
		for _, entry in ipairs(closing) do
			problems.closingIndustries[#problems.closingIndustries + 1] = entry[1]
		end
	end
	ctx.snapshot.problems = problems
end

-- ---------------------------------------------------------------------------
-- snapshot orchestration

local function readClock()
	local gameTime = getComponent(api.engine.util.getWorld(), api.type.ComponentType.GAME_TIME)
	return gameTime.gameTime, api.util.getDefaultYearDuration()
end

-- ---------------------------------------------------------------------------
-- stocks, depots, vehicle catalog

--- Appends one row per stock of `stockEntity` (an entity with a STOCK_LIST component).
--- Stock ids passed to simEntityAtStockSystem are 0-based (see the game's cargo_util.tl).
local function addStocks(ctx, kind, ownerId, ownerName, stockEntity)
	local list = getComponent(stockEntity, api.type.ComponentType.STOCK_LIST)
	if not list then
		return
	end
	for index, stock in ipairs(list.stocks) do
		local stockId = index - 1
		local label = kind .. "[" .. tostring(ownerId) .. "].stock[" .. stockId .. "]"
		local cargos = {}
		local types = try(ctx, label .. ".cargoTypes", api.engine.util.stock.getStockCargoTypes, stockEntity, stockId)
		for _, cargoId in ipairs(types or {}) do
			cargos[#cargos + 1] = cargoRef(ctx, cargoId)
		end
		ctx.snapshot.stocks[#ctx.snapshot.stocks + 1] = {
			kind = kind,
			owner = ownerId,
			ownerName = ownerName,
			stockId = stockId,
			stockType = stock.type,
			cargos = cargos,
			count = try(ctx, label .. ".count", api.engine.system.simEntityAtStockSystem.getStockCount, stockEntity, stockId),
			capacity = stock.capacity,
		}
	end
end

local function collectStocks(ctx)
	ctx.snapshot.stocks = {}
	for groupId in pairs(ctx.stationGroups) do
		local group = try(ctx, "stocks.group[" .. tostring(groupId) .. "]", getComponent, groupId, api.type.ComponentType.STATION_GROUP)
		local name = entityName(groupId)
		for _, stationId in ipairs(group and group.stations or {}) do
			try(ctx, "stocks.station[" .. tostring(stationId) .. "]", addStocks, ctx, "station", groupId, name, stationId)
		end
	end
	for _, industry in ipairs(ctx.snapshot.industries or {}) do
		if industry.stockList then
			try(ctx, "stocks.industry[" .. tostring(industry.id) .. "]", addStocks, ctx, "industry", industry.id, industry.name, industry.stockList)
		end
	end
	local warehouses = try(ctx, "stocks.warehouses", api.engine.getEntitiesWithComponent, api.type.ComponentType.WAREHOUSE) or {}
	for _, warehouseId in ipairs(warehouses) do
		local warehouse = try(ctx, "stocks.warehouse[" .. tostring(warehouseId) .. "]", getComponent, warehouseId, api.type.ComponentType.WAREHOUSE)
		if warehouse and warehouse.stockList then
			try(ctx, "stocks.warehouse[" .. tostring(warehouseId) .. "].stock", addStocks, ctx, "warehouse", warehouseId, entityName(warehouseId), warehouse.stockList)
		end
	end
end

local function collectDepots(ctx)
	local depots = {}
	for depotId in pairs(ctx.depots) do
		local label = "depot[" .. tostring(depotId) .. "]"
		local out = { id = depotId, name = entityName(depotId) }
		local depot = try(ctx, label .. ".component", getComponent, depotId, api.type.ComponentType.VEHICLE_DEPOT)
		if depot then
			out.carrier = carrierName(depot.carrier)
		end
		local constructionId = try(ctx, label .. ".construction", api.engine.util.construction.getConstructionEntity, depotId)
		local construction = constructionId and try(ctx, label .. ".constructionComponent", getComponent, constructionId, api.type.ComponentType.CONSTRUCTION)
		if construction then
			pcall(function()
				local transf = construction.transf
				out.position = { transf[13], transf[14], transf[15] }
			end)
		end
		depots[#depots + 1] = out
	end
	ctx.snapshot.depots = depots
end

--- Models a player can buy as a vehicle (or as part of one), with the figures that matter for fit.
--- Includes models already available in `year` and those arriving within CATALOG_LOOKAHEAD_YEARS.
local CATALOG_LOOKAHEAD_YEARS = 10

local function modelCapacities(tv)
	local totals = {}
	for _, compartment in ipairs(tv.compartments or {}) do
		local best = {}
		for _, loadConfig in ipairs(compartment.loadConfigs or {}) do
			local entry = loadConfig.cargoEntry
			if entry and entry.cargoTypeSet then
				api.res.cargoTypeRep.forEachCargoType(entry.cargoTypeSet, function(cargoId)
					best[cargoId] = math.max(best[cargoId] or 0, entry.capacity or 0)
				end)
			end
		end
		for cargoId, capacity in pairs(best) do
			totals[cargoId] = (totals[cargoId] or 0) + capacity
		end
	end
	return totals
end

local function catalogEntry(ctx, name, year)
	local id = api.res.modelRep.find(name)
	if id == nil or id < 0 then
		return nil
	end
	local model = api.res.modelRep.get(id)
	local md = model.metadata
	local tv = md.transportVehicle
	if not tv then
		return nil
	end
	local availability = md.availability
	local yearFrom = availability and availability.yearFrom or -1
	local yearTo = availability and availability.yearTo or -1
	local available = (yearFrom <= 0 or year >= yearFrom) and (yearTo <= 0 or year < yearTo)
	if not available and not (yearFrom > year and yearFrom <= year + CATALOG_LOOKAHEAD_YEARS) then
		return nil
	end
	if not api.res.modelRep.isVisible(id) then
		return nil
	end
	local entry = {
		id = id,
		res = name,
		name = md.description and md.description.name,
		carrier = carrierName(tv.carrier),
		available = available,
		yearFrom = yearFrom,
		yearTo = yearTo,
		groupFileName = tv.groupFileName,
		comfort = tv.comfortFactor,
		priceFactor = tv.priceFactor,
		reversible = tv.reversible,
		capacity = {},
	}
	if md.cost then
		entry.price = md.cost.price
	end
	if md.maintenance then
		entry.lifespan = md.maintenance.lifespan
		entry.runningCosts = md.maintenance.runningCosts
	end
	local motion = md.landVehicle or md.waterVehicle or md.airVehicle
	if motion then
		entry.topSpeed = motion.topSpeed
		entry.weightEmpty = motion.weightEmpty
		entry.weightMaxPayload = motion.weightMaxPayload
	end
	if md.airVehicle then
		entry.helicopter = md.airVehicle.isHelicopter
	end
	if md.landVehicle and md.landVehicle.engines then
		local power, effort = 0, 0
		for _, engine in ipairs(md.landVehicle.engines) do
			power = power + (engine.power or 0)
			effort = effort + (engine.tractiveEffort or 0)
		end
		entry.power = power
		entry.tractiveEffort = effort
	end
	for cargoId, capacity in pairs(modelCapacities(tv)) do
		entry.capacity[#entry.capacity + 1] = { cargo = cargoRef(ctx, cargoId), capacity = capacity }
	end
	return entry
end

local function collectCatalog(ctx)
	local catalog = {}
	local year = ctx.snapshot.meta.year
	api.res.modelRep.forEachModelWithMetadata("transportVehicle", function(name)
		local ok, entry = pcall(catalogEntry, ctx, name, year)
		if not ok then
			addError(ctx, "catalog[" .. tostring(name) .. "]", entry)
		elseif entry then
			catalog[#catalog + 1] = entry
		end
	end)
	ctx.snapshot.catalog = catalog
end

local function buildSnapshot(reason, requestId)
	local now, yearDuration = readClock()
	local ctx = {
		now = now,
		yearDuration = yearDuration,
		fromTime = math.max(now - yearDuration, 0),
		player = api.engine.util.getPlayer(),
		errors = {},
		cargoSeen = {},
		modelSeen = {},
		stationGroups = {},
		depots = {},
		snapshot = { cargos = {}, models = {} },
	}
	collectMeta(ctx, reason, requestId)
	try(ctx, "company", collectCompany, ctx)
	try(ctx, "lines", collectLines, ctx)
	try(ctx, "vehicles", collectVehicles, ctx)
	try(ctx, "stations", collectStations, ctx)
	try(ctx, "industries", collectIndustries, ctx)
	try(ctx, "towns", collectTowns, ctx)
	try(ctx, "problems", collectProblems, ctx)
	try(ctx, "stocks", collectStocks, ctx)
	try(ctx, "depots", collectDepots, ctx)
	if reason ~= "interval" then
		-- the catalog only changes with the year; interval snapshots skip it to stay small
		try(ctx, "catalog", collectCatalog, ctx)
	end
	ctx.snapshot.errors = ctx.errors
	return ctx.snapshot, now
end

-- ---------------------------------------------------------------------------
-- snapshot output
--
-- The map editor's town/industry export directory is accepted by app.saveUserdata.
-- Use this single sink to avoid visible errors from unsupported directories.


--- app.loadUserdata on a missing file raises a visible in-game error even under pcall,
--- so check the directory listing first.
local function readRequestId()
	local okList, names = pcall(app.getAllUserdata, DIR)
	if not okList or type(names) ~= "table" then
		return nil
	end
	local present = false
	for _, name in ipairs(names) do
		if name == REQUEST_FILE or name == REQUEST_FILE .. ".lua" then
			present = true
			break
		end
	end
	if not present then
		return nil
	end
	local ok, request = pcall(app.loadUserdata, DIR, REQUEST_FILE)
	if ok and type(request) == "table" then
		return request.id
	end
	return nil
end


function bridge.guiUpdate(_params, _state, guiState)
	local state = guiState:get() or {}
	state.frame = (state.frame or 0) + 1

	if app == nil or app.saveUserdata == nil then
		if not state.warnedNoApp then
			log("app module is not available in the GUI state; bridge disabled")
			state.warnedNoApp = true
		end
		guiState:set(state)
		return
	end

	local okClock, now, yearDuration = pcall(readClock)
	if not okClock then
		guiState:set(state)
		return
	end

	local reason
	local requestId
	if state.lastGameTime == nil or now < state.lastGameTime then
		reason = "start"
	elseif now - state.lastGameTime >= yearDuration / SNAPSHOTS_PER_YEAR then
		reason = "interval"
	end
	if state.frame % REQUEST_POLL_FRAMES == 0 then
		local id = readRequestId()
		if id ~= nil and id ~= state.lastRequestId then
			reason = "request"
			requestId = id
		end
	end

	if reason and (state.retryFrame == nil or state.frame >= state.retryFrame) then
		local ok, err = pcall(function()
			local snapshot, gameTime = buildSnapshot(reason, requestId)
			app.saveUserdata(DIR, string.format("tf3c_snap_%015d", gameTime), snapshot)
			log(string.format("snapshot written (reason=%s, gameTime=%d, lines=%d, vehicles=%d, errors=%d)",
				reason, gameTime, #(snapshot.lines or {}), #(snapshot.vehicles or {}), #snapshot.errors))
		end)
		if ok then
			state.lastGameTime = now
			state.lastRequestId = requestId or state.lastRequestId
			state.retryFrame = nil
		else
			log("snapshot failed: " .. tostring(err))
			state.retryFrame = state.frame + REQUEST_POLL_FRAMES
		end
	end

	guiState:set(state)
end

-- .script.lua resources expose their exports through data(), not a return value
function data()
	return bridge
end
