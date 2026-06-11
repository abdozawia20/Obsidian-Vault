# Flat — Flutter: Technical Document

> **Product**: Asset Rental Platform  
> **Module**: Flat Flutter Feature Set  
> **Document Type**: Technical  
> **Audience**: Flutter developers  
> **Companion**: [flat-flutter-functional.md](./flat-flutter-functional.md)

---

## 1. Feature Directory Structure

```
lib/features/flats/
├── flat_catalog_screen.dart
├── flat_detail_screen.dart
├── floor_plan_viewer_screen.dart
├── utility_readings_screen.dart
├── appliances_screen.dart
└── widgets/
    ├── flat_spec_card.dart
    ├── building_amenities_row.dart
    ├── flat_filter_sheet.dart
    ├── utility_reading_tile.dart
    ├── utility_chart_widget.dart
    └── appliance_tile.dart
```

---

## 2. Models

```dart
// core/models/flat_asset.dart
@freezed
class FlatAsset with _$FlatAsset {
  const factory FlatAsset({
    required String name,
    required String assetName,
    required String location,
    required double monthlyRate,
    required double depositAmount,
    String? property,
    String? building,
    String? unitNumber,
    int? floorNumber,
    double? areaSqm,
    double? livingAreaSqm,
    int? bedrooms,
    int? bathrooms,
    bool hasBalcony = false,
    bool hasStorageRoom = false,
    bool parkingIncluded = false,
    String? parkingSlotNumber,
    String? furnished,         // Unfurnished / Semi-Furnished / Fully Furnished
    String? directionFacing,
    String? viewType,
    bool utilitiesIncluded = false,
    int? maxOccupants,
    bool petsAllowed = false,
    bool smokingAllowed = false,
    int? keyCount,
    String? floorPlanUrl,
    String? previewMode,
    String? previewUrl,
    List<FlatAppliance> appliances = const [],
    List<String> buildingAmenities = const [],
    List<String> images = const [],
  }) = _FlatAsset;

  factory FlatAsset.fromJson(Map<String, dynamic> json) =>
      _$FlatAssetFromJson(json);
}

@freezed
class FlatAppliance with _$FlatAppliance {
  const factory FlatAppliance({
    required String name,
    String? brand,
    String? model,
    String? serialNumber,
    DateTime? warrantyExpiry,
    required String condition,   // New, Good, Fair, Needs Repair
  }) = _FlatAppliance;

  factory FlatAppliance.fromJson(Map<String, dynamic> json) =>
      _$FlatApplianceFromJson(json);
}

@freezed
class UtilityReading with _$UtilityReading {
  const factory UtilityReading({
    required DateTime readingDate,
    required String meterType,
    required double previousReading,
    required double currentReading,
    required double consumption,
    required double unitRate,
    required double totalCharge,
  }) = _UtilityReading;

  factory UtilityReading.fromJson(Map<String, dynamic> json) =>
      _$UtilityReadingFromJson(json);
}
```

---

## 3. Riverpod Providers

```dart
// Flat filter state
@riverpod
class FlatFilterNotifier extends _$FlatFilterNotifier {
  @override
  FlatFilter build() => const FlatFilter();
  void setBedrooms(int? v)        => state = state.copyWith(bedrooms: v);
  void setFurnished(String? v)    => state = state.copyWith(furnished: v);
  void setAreaRange(double min, double max) =>
      state = state.copyWith(minArea: min, maxArea: max);
  void setParkingIncluded(bool v) => state = state.copyWith(parkingIncluded: v);
  void setPetsAllowed(bool v)     => state = state.copyWith(petsAllowed: v);
  void setMaxPrice(double? v)     => state = state.copyWith(maxPrice: v);
  void reset()                    => state = const FlatFilter();
}

// Flat asset providers
@riverpod
Future<List<FlatAsset>> flatAssets(Ref ref, FlatFilter filter) =>
    FlatsApi().getFlats(filter);

@riverpod
Future<FlatAsset> flatDetail(Ref ref, String assetName) =>
    FlatsApi().getFlatDetail(assetName);

// Utility history provider (parameterized by agreement)
@riverpod
Future<List<UtilityReading>> utilityHistory(Ref ref, String agreementId) =>
    FlatsApi().getUtilityHistory(agreementId);
```

---

## 4. Flat Catalog Screen

```dart
class FlatCatalogScreen extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final filter = ref.watch(flatFilterNotifierProvider);
    final assets = ref.watch(flatAssetsProvider(filter));

    return Scaffold(
      appBar: AppBar(
        title: const Text('Flats'),
        actions: [
          IconButton(
            icon: const Icon(Icons.tune),
            onPressed: () => showModalBottomSheet(
              context: context,
              isScrollControlled: true,
              builder: (_) => FlatFilterSheet(filter: filter),
            ),
          ),
        ],
      ),
      body: Column(children: [
        // Active filter chips row
        _ActiveFlatFilterChips(filter: filter),
        Expanded(
          child: assets.when(
            data: (list) => list.isEmpty
                ? const Center(child: Text('No flats match your filters'))
                : GridView.builder(
                    padding: const EdgeInsets.all(12),
                    gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: 2, childAspectRatio: 0.72,
                      crossAxisSpacing: 12, mainAxisSpacing: 12),
                    itemCount: list.length,
                    itemBuilder: (_, i) => _FlatCard(flat: list[i]),
                  ),
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (e, _) => ErrorView(message: '$e'),
          ),
        ),
      ]),
    );
  }
}
```

---

## 5. Flat Detail Screen

```dart
class FlatDetailScreen extends ConsumerWidget {
  final String assetId;
  const FlatDetailScreen({required this.assetId, super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final flat = ref.watch(flatDetailProvider(assetId));
    return flat.when(
      data: (f) => Scaffold(
        body: CustomScrollView(slivers: [
          SliverAppBar(
            expandedHeight: 280,
            flexibleSpace: FlexibleSpaceBar(
              background: PhotoGalleryWidget(images: f.images)),
          ),
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                _buildHeader(f),
                const SizedBox(height: 16),
                _buildSpecGrid(f),
                const SizedBox(height: 16),
                BuildingAmenitiesRow(amenities: f.buildingAmenities),
                if (f.utilitiesIncluded) ...[
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    decoration: BoxDecoration(
                      color: Colors.green.shade50,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: Colors.green.shade200)),
                    child: Row(children: [
                      Icon(Icons.check_circle, color: Colors.green.shade600, size: 18),
                      const SizedBox(width: 8),
                      const Text('Utilities included in rent',
                          style: TextStyle(color: Colors.green)),
                    ]),
                  ),
                ],
                const SizedBox(height: 16),
                if (f.appliances.isNotEmpty) _buildAppliancesButton(context, f),
                if (f.floorPlanUrl != null) _buildFloorPlanButton(context, f.floorPlanUrl!),
                const SizedBox(height: 16),
                AvailabilityCalendarWidget(assetName: f.name),
                const SizedBox(height: 24),
                _buildBookCTA(context, f),
              ]),
            ),
          ),
        ]),
      ),
      loading: () => const Scaffold(body: Center(child: CircularProgressIndicator())),
      error: (e, _) => ErrorView(message: '$e'),
    );
  }

  Widget _buildSpecGrid(FlatAsset f) => Wrap(spacing: 10, runSpacing: 10, children: [
    FlatSpecCard(icon: '🛏', label: 'Bedrooms',   value: '${f.bedrooms ?? "—"}'),
    FlatSpecCard(icon: '🛁', label: 'Bathrooms',  value: '${f.bathrooms ?? "—"}'),
    FlatSpecCard(icon: '📐', label: 'Area',       value: '${f.areaSqm?.toStringAsFixed(0) ?? "—"} m²'),
    FlatSpecCard(icon: '🏢', label: 'Floor',      value: '${f.floorNumber ?? "—"}'),
    FlatSpecCard(icon: '🛋', label: 'Furnishing', value: f.furnished ?? '—'),
    FlatSpecCard(icon: '🌅', label: 'View',       value: f.viewType ?? '—'),
    if (f.parkingIncluded) FlatSpecCard(icon: '🅿', label: 'Parking', value: 'Included'),
    if (f.petsAllowed)     FlatSpecCard(icon: '🐾', label: 'Pets',    value: 'Allowed'),
  ]);

  Widget _buildAppliancesButton(BuildContext context, FlatAsset f) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: OutlinedButton.icon(
      icon: const Icon(Icons.kitchen),
      label: Text('Appliances (${f.appliances.length})'),
      onPressed: () => context.push('/appliances', extra: f.appliances),
    ),
  );

  Widget _buildFloorPlanButton(BuildContext context, String url) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: OutlinedButton.icon(
      icon: const Icon(Icons.picture_as_pdf),
      label: const Text('View Floor Plan'),
      onPressed: () => context.push('/floor-plan?url=${Uri.encodeComponent(url)}'),
    ),
  );
}
```

---

## 6. Building Amenities Row

```dart
class BuildingAmenitiesRow extends StatelessWidget {
  final List<String> amenities;
  const BuildingAmenitiesRow({required this.amenities, super.key});

  @override
  Widget build(BuildContext context) {
    if (amenities.isEmpty) return const SizedBox.shrink();
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Text('Building Amenities',
          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
      const SizedBox(height: 8),
      SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(
          children: amenities.map((a) => Container(
            margin: const EdgeInsets.only(right: 8),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            decoration: BoxDecoration(
              color: Colors.blue.shade50,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: Colors.blue.shade200)),
            child: Text(a, style: TextStyle(
              fontSize: 13, color: Colors.blue.shade800,
              fontWeight: FontWeight.w500)),
          )).toList(),
        ),
      ),
    ]);
  }
}
```

---

## 7. Flat Filter Sheet

```dart
class FlatFilterSheet extends ConsumerWidget {
  final FlatFilter filter;
  const FlatFilterSheet({required this.filter, super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final notifier = ref.read(flatFilterNotifierProvider.notifier);
    return DraggableScrollableSheet(
      initialChildSize: 0.85,
      expand: false,
      builder: (_, controller) => ListView(
        controller: controller,
        padding: const EdgeInsets.all(20),
        children: [
          Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
            const Text('Filter Flats',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            TextButton(onPressed: notifier.reset, child: const Text('Reset')),
          ]),
          const SizedBox(height: 16),
          // Bedrooms
          const Text('Bedrooms', style: TextStyle(fontWeight: FontWeight.w600)),
          const SizedBox(height: 8),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: {'Studio': 0, '1': 1, '2': 2, '3': 3, '4': 4, '5+': 5}
                  .entries.map((e) => Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: ChoiceChip(
                      label: Text(e.key),
                      selected: filter.bedrooms == e.value,
                      onSelected: (_) => notifier.setBedrooms(e.value),
                    ),
                  )).toList(),
            ),
          ),
          const SizedBox(height: 16),
          // Furnishing
          const Text('Furnishing', style: TextStyle(fontWeight: FontWeight.w600)),
          const SizedBox(height: 8),
          DropdownButtonFormField<String>(
            value: filter.furnished,
            decoration: const InputDecoration(border: OutlineInputBorder()),
            items: [null, 'Unfurnished', 'Semi-Furnished', 'Fully Furnished']
                .map((v) => DropdownMenuItem(value: v, child: Text(v ?? 'Any')))
                .toList(),
            onChanged: notifier.setFurnished,
          ),
          const SizedBox(height: 16),
          // Area range
          const Text('Area (m²)', style: TextStyle(fontWeight: FontWeight.w600)),
          const SizedBox(height: 8),
          RangeSlider(
            values: RangeValues(filter.minArea ?? 0, filter.maxArea ?? 500),
            min: 0, max: 500, divisions: 50,
            labels: RangeLabels(
                '${(filter.minArea ?? 0).toInt()} m²',
                '${(filter.maxArea ?? 500).toInt()} m²'),
            onChanged: (v) => notifier.setAreaRange(v.start, v.end),
          ),
          // Toggles
          SwitchListTile(
            title: const Text('Parking Included'),
            value: filter.parkingIncluded ?? false,
            onChanged: notifier.setParkingIncluded,
          ),
          SwitchListTile(
            title: const Text('Pets Allowed'),
            value: filter.petsAllowed ?? false,
            onChanged: notifier.setPetsAllowed,
          ),
          const SizedBox(height: 20),
          SizedBox(
            width: double.infinity,
            child: FilledButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Apply Filters'),
            ),
          ),
        ],
      ),
    );
  }
}
```

---

## 8. Utility Readings Screen

```dart
class UtilityReadingsScreen extends ConsumerWidget {
  final String agreementId;
  final bool utilitiesIncluded;
  const UtilityReadingsScreen({
    required this.agreementId,
    this.utilitiesIncluded = false,
    super.key,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (utilitiesIncluded) {
      return Scaffold(
        appBar: AppBar(title: const Text('Utility Usage')),
        body: const Center(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Icon(Icons.check_circle_outline, size: 64, color: Colors.green),
            SizedBox(height: 16),
            Text('Utilities are included in your rent.',
                style: TextStyle(fontSize: 16)),
          ]),
        ),
      );
    }

    final history = ref.watch(utilityHistoryProvider(agreementId));
    return DefaultTabController(
      length: 3,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Utility Usage'),
          bottom: const TabBar(tabs: [
            Tab(text: '⚡ Electricity'),
            Tab(text: '💧 Water'),
            Tab(text: '🔥 Gas'),
          ]),
        ),
        body: history.when(
          data: (readings) => TabBarView(
            children: ['Electricity', 'Water', 'Gas'].map((meter) {
              final meterReadings =
                  readings.where((r) => r.meterType == meter).toList();
              if (meterReadings.isEmpty) {
                return Center(child: Text('No $meter readings yet'));
              }
              return ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  UtilityChartWidget(readings: meterReadings),
                  const SizedBox(height: 16),
                  ...meterReadings.map((r) => UtilityReadingTile(reading: r)),
                ],
              );
            }).toList(),
          ),
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => ErrorView(message: '$e'),
        ),
      ),
    );
  }
}
```

---

## 9. Utility Chart Widget (`fl_chart`)

```dart
// pubspec.yaml: fl_chart: ^0.67.0

class UtilityChartWidget extends StatelessWidget {
  final List<UtilityReading> readings;
  const UtilityChartWidget({required this.readings, super.key});

  @override
  Widget build(BuildContext context) {
    final sorted = readings.reversed.toList(); // oldest → newest for chart
    return SizedBox(
      height: 180,
      child: BarChart(BarChartData(
        barGroups: sorted.asMap().entries.map((e) => BarChartGroupData(
          x: e.key,
          barRods: [BarChartRodData(
            toY: e.value.consumption,
            color: Theme.of(context).colorScheme.primary,
            width: 18,
            borderRadius: BorderRadius.circular(4),
          )],
        )).toList(),
        titlesData: FlTitlesData(
          bottomTitles: AxisTitles(sideTitles: SideTitles(
            showTitles: true, reservedSize: 28,
            getTitlesWidget: (v, _) {
              final i = v.toInt();
              if (i < 0 || i >= sorted.length) return const SizedBox.shrink();
              return Text(DateFormatter.shortMonth(sorted[i].readingDate),
                  style: const TextStyle(fontSize: 10));
            },
          )),
          leftTitles: AxisTitles(sideTitles: SideTitles(
            showTitles: true, reservedSize: 40)),
          rightTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
          topTitles:   AxisTitles(sideTitles: SideTitles(showTitles: false)),
        ),
        gridData: FlGridData(show: false),
        borderData: FlBorderData(show: false),
      )),
    );
  }
}
```

---

## 10. Appliance Tile

```dart
class ApplianceTile extends StatelessWidget {
  final FlatAppliance appliance;
  const ApplianceTile({required this.appliance, super.key});

  @override
  Widget build(BuildContext context) {
    final daysLeft = appliance.warrantyExpiry != null
        ? appliance.warrantyExpiry!.difference(DateTime.now()).inDays
        : null;
    final warrantyColor = daysLeft == null
        ? Colors.grey
        : daysLeft > 30
            ? Colors.green
            : daysLeft > 0
                ? Colors.orange
                : Colors.red;
    final conditionColor = {
      'New': Colors.green, 'Good': Colors.blue,
      'Fair': Colors.orange, 'Needs Repair': Colors.red,
    }[appliance.condition] ?? Colors.grey;

    return ListTile(
      leading: const CircleAvatar(child: Icon(Icons.kitchen, size: 20)),
      title: Text(appliance.name,
          style: const TextStyle(fontWeight: FontWeight.w600)),
      subtitle: Text('${appliance.brand ?? ""} ${appliance.model ?? ""}'.trim()),
      trailing: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: conditionColor.withOpacity(0.12),
            borderRadius: BorderRadius.circular(6)),
          child: Text(appliance.condition,
              style: TextStyle(fontSize: 11, color: conditionColor,
                  fontWeight: FontWeight.w600)),
        ),
        if (daysLeft != null) ...[
          const SizedBox(height: 4),
          Text(
            daysLeft > 0 ? '${daysLeft}d warranty' : 'Warranty expired',
            style: TextStyle(fontSize: 10, color: warrantyColor),
          ),
        ],
      ]),
    );
  }
}
```

---

## 11. API Layer (`core/api/flats_api.dart`)

```dart
class FlatsApi {
  final _client = FrappeClient();

  Future<List<FlatAsset>> getFlats(FlatFilter filter) async {
    final data = await _client.get(
      'rental_core.api.assets.get_available_assets',
      params: {'asset_type': 'Flat', ...filter.toMap()},
    );
    return (data['assets'] as List).map(FlatAsset.fromJson).toList();
  }

  Future<FlatAsset> getFlatDetail(String assetName) async {
    final data = await _client.get(
      'rental_flats.api.flats.get_flat_detail',
      params: {'asset_name': assetName},
    );
    return FlatAsset.fromJson(data as Map<String, dynamic>);
  }

  Future<List<UtilityReading>> getUtilityHistory(String agreementId) async {
    final data = await _client.get(
      'rental_flats.api.flats.get_utility_history',
      params: {'agreement': agreementId},
    );
    return (data as List).map(UtilityReading.fromJson).toList();
  }
}
```

---

## 12. Route Registration

```dart
// Added to app_router.dart
GoRoute(
  path: '/floor-plan',
  builder: (_, s) => FloorPlanViewerScreen(
    url: s.uri.queryParameters['url'] ?? ''),
),
GoRoute(
  path: '/agreement/:id/utilities',
  builder: (_, s) => UtilityReadingsScreen(
    agreementId: s.pathParameters['id']!,
    utilitiesIncluded: s.uri.queryParameters['included'] == 'true'),
),
GoRoute(
  path: '/appliances',
  builder: (_, s) => AppliancesScreen(
    appliances: s.extra as List<FlatAppliance>),
),
```

---

## 13. Implementation Phases

| Phase | Deliverables |
|---|---|
| **1** | Flat catalog with filter sheet, flat detail with spec grid + amenities row |
| **2** | Appliances screen, floor plan PDF viewer, `FlatAsset` model with all fields |
| **3** | Utility readings screen with fl_chart bar chart + reading tiles |
| **4** | 3D preview WebView, agreement detail "Utilities" tab, warranty countdown chip |

---

## 14. Testing Checklist

- [ ] Flat filter sheet applies bedrooms, furnishing, area, parking, pets correctly
- [ ] Active filter chips render and dismiss individual filters
- [ ] Flat detail shows building amenities from API response
- [ ] Appliances screen renders all appliances with correct condition badge and warranty countdown
- [ ] Warranty countdown turns orange ≤30 days, red when expired
- [ ] Floor plan button opens PDF viewer (or device viewer) with the attached URL
- [ ] Utility readings screen shows tabbed layout per meter type
- [ ] fl_chart bar chart renders with correct month labels and consumption data
- [ ] Utility readings are read-only — no submit action available for Customer role
- [ ] "Utilities included" message shown instead of data when flag is set
- [ ] 3D preview WebView opens with correct URL per preview mode configuration
