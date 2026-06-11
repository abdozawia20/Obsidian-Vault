# Vehicle — Flutter: Technical Document

> **Product**: Asset Rental Platform  
> **Module**: Vehicle Flutter Feature Set  
> **Document Type**: Technical  
> **Audience**: Flutter developers  
> **Companion**: [vehicle-flutter-functional.md](./vehicle-flutter-functional.md)

---

## 1. Feature Directory Structure

```
lib/features/vehicles/
├── vehicle_catalog_screen.dart
├── vehicle_detail_screen.dart
├── vehicle_booking_step2.dart         # Replaces base Step 2 for vehicle bookings
├── mileage_log_screen.dart
├── traffic_violation_screen.dart
└── widgets/
    ├── vehicle_spec_card.dart
    ├── mileage_policy_card.dart
    ├── vehicle_filter_sheet.dart
    ├── vehicle_map_screen.dart        # Fleet Manager only
    └── mileage_log_tile.dart
```

---

## 2. Models

```dart
// core/models/vehicle_asset.dart
@freezed
class VehicleAsset with _$VehicleAsset {
  const factory VehicleAsset({
    required String name,
    required String assetName,
    required String location,
    required double monthlyRate,
    required double depositAmount,
    String? category,
    String? plateNumber,
    String? make,
    String? model,
    int? year,
    String? fuelType,
    String? transmission,
    int? seats,
    double? engineCc,
    // VIN intentionally omitted — not served to Customer role
    double? currentMileageKm,
    DateTime? insuranceExpiry,
    bool hasGps = false,
    VehicleCategory? categoryDetail,
    List<String> images = const [],
    String? previewMode,
    String? previewUrl,
  }) = _VehicleAsset;

  factory VehicleAsset.fromJson(Map<String, dynamic> json) =>
      _$VehicleAssetFromJson(json);
}

@freezed
class VehicleCategory with _$VehicleCategory {
  const factory VehicleCategory({
    required String name,
    required double includedKmPerDay,
    required double overageRatePerKm,
    required String fuelPolicy,
    int minDriverAge = 18,
    String requiredLicenseClass = '',
  }) = _VehicleCategory;

  factory VehicleCategory.fromJson(Map<String, dynamic> json) =>
      _$VehicleCategoryFromJson(json);
}

@freezed
class MileageLog with _$MileageLog {
  const factory MileageLog({
    required String name,
    required String logType,    // Pickup, Return, Mid-Term Check
    required DateTime logDate,
    required double odometerKm,
    required int fuelLevelPct,
    double? drivenKm,
    double? overageKm,
    double? overageCharge,
  }) = _MileageLog;

  factory MileageLog.fromJson(Map<String, dynamic> json) =>
      _$MileageLogFromJson(json);
}
```

---

## 3. Riverpod Providers

```dart
// Vehicle-specific filter state
@riverpod
class VehicleFilterNotifier extends _$VehicleFilterNotifier {
  @override
  VehicleFilter build() => const VehicleFilter();
  void setCategory(String? v)     => state = state.copyWith(category: v);
  void setFuelType(String? v)     => state = state.copyWith(fuelType: v);
  void setTransmission(String? v) => state = state.copyWith(transmission: v);
  void setMinSeats(int? v)        => state = state.copyWith(minSeats: v);
  void setMaxPrice(double? v)     => state = state.copyWith(maxPrice: v);
}

@riverpod
Future<List<VehicleAsset>> vehicleAssets(Ref ref, VehicleFilter filter) =>
    VehiclesApi().getVehicles(filter);

@riverpod
Future<VehicleAsset> vehicleDetail(Ref ref, String assetName) =>
    VehiclesApi().getVehicleDetail(assetName);

@riverpod
Future<List<MileageLog>> mileageLogs(Ref ref, String agreementId) =>
    VehiclesApi().getMileageLogs(agreementId);
```

---

## 4. Vehicle Catalog Screen

```dart
class VehicleCatalogScreen extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final filter = ref.watch(vehicleFilterNotifierProvider);
    final assets = ref.watch(vehicleAssetsProvider(filter));
    return Scaffold(
      appBar: AppBar(
        title: const Text('Vehicles'),
        actions: [
          IconButton(
            icon: const Icon(Icons.tune),
            onPressed: () => showModalBottomSheet(
              context: context, isScrollControlled: true,
              builder: (_) => VehicleFilterSheet(filter: filter),
            ),
          ),
        ],
      ),
      body: Column(children: [
        // Active filter chips
        _ActiveFilterChips(filter: filter),
        Expanded(
          child: assets.when(
            data: (list) => GridView.builder(
              padding: const EdgeInsets.all(12),
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 2, childAspectRatio: 0.75,
                crossAxisSpacing: 12, mainAxisSpacing: 12),
              itemCount: list.length,
              itemBuilder: (_, i) => AssetCard(asset: list[i]),
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

## 5. Mileage Policy Card Widget

```dart
class MileagePolicyCard extends StatelessWidget {
  final VehicleCategory category;
  const MileagePolicyCard({required this.category, super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.all(16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.orange.shade50,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.orange.shade200),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('📏 Mileage & Fuel Policy',
          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
        const SizedBox(height: 12),
        Row(children: [
          Expanded(child: _PolicyTile(
            label: 'Included/day',
            value: '${category.includedKmPerDay.toInt()} km')),
          Expanded(child: _PolicyTile(
            label: 'Overage rate',
            value: '+${CurrencyFormatter.format(category.overageRatePerKm)}/km',
            valueColor: Colors.orange.shade700)),
        ]),
        const SizedBox(height: 8),
        Text('⛽ Fuel policy: ${category.fuelPolicy}',
          style: TextStyle(fontSize: 13, color: Colors.grey.shade700)),
      ]),
    );
  }
}
```

---

## 6. Vehicle Booking Step 2 (Driver License Fields)

This widget **replaces** the base `StepDetails` widget for vehicle bookings. The booking flow screen checks `AppConfig.hasVehicles && asset.assetType == 'Vehicle'` to swap in this version.

```dart
class VehicleBookingStep2 extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final notifier = ref.read(bookingNotifierProvider.notifier);
    final booking  = ref.watch(bookingNotifierProvider);
    return Column(children: [
      // Base fields (name, phone, tenant type)
      _BasePersonalFields(ref: ref),
      const Divider(height: 32),
      const Text('🪪 Driver License',
        style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
      const SizedBox(height: 12),
      TextFormField(
        decoration: const InputDecoration(labelText: 'License Number'),
        onChanged: notifier.setLicenseNumber,
        validator: (v) => v?.isEmpty == true ? 'Required' : null,
      ),
      const SizedBox(height: 12),
      TextFormField(
        decoration: InputDecoration(
          labelText: 'License Class',
          hintText: booking.requiredLicenseClass ?? 'e.g. B'),
        onChanged: notifier.setLicenseClass,
      ),
      const SizedBox(height: 12),
      // License expiry date picker with validation
      _DateField(
        label: 'License Expiry',
        firstDate: DateTime.now(),
        lastDate: DateTime.now().add(const Duration(days: 365 * 20)),
        onChanged: notifier.setLicenseExpiry,
        validator: (d) {
          if (d == null) return 'Required';
          final end = booking.startDate!
              .add(Duration(days: 30 * booking.durationMonths));
          if (d.isBefore(end)) {
            return 'License must cover the full rental period '
                '(ends ${DateFormatter.format(end)})';
          }
          return null;
        },
      ),
      const SizedBox(height: 12),
      // Date of birth with age validation
      _DateField(
        label: 'Date of Birth',
        firstDate: DateTime(1920),
        lastDate: DateTime.now().subtract(
            Duration(days: 365 * (booking.minDriverAge ?? 18))),
        onChanged: notifier.setDriverDob,
        validator: (d) {
          if (d == null) return 'Required';
          final age = DateTime.now().difference(d).inDays / 365.25;
          if (age < (booking.minDriverAge ?? 18)) {
            return 'Driver must be at least ${booking.minDriverAge ?? 18} years old';
          }
          return null;
        },
      ),
    ]);
  }
}
```

---

## 7. Mileage Log Screen

```dart
class MileageLogScreen extends ConsumerWidget {
  final String agreementId;
  const MileageLogScreen({required this.agreementId, super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final logs = ref.watch(mileageLogsProvider(agreementId));
    return Scaffold(
      appBar: AppBar(title: const Text('Mileage History')),
      body: logs.when(
        data: (list) => ListView.separated(
          padding: const EdgeInsets.all(16),
          itemCount: list.length,
          separatorBuilder: (_, __) => const Divider(),
          itemBuilder: (_, i) => MileageLogTile(log: list[i]),
        ),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => ErrorView(message: '$e'),
      ),
    );
  }
}

class MileageLogTile extends StatelessWidget {
  final MileageLog log;
  const MileageLogTile({required this.log, super.key});

  @override
  Widget build(BuildContext context) {
    final isReturn = log.logType == 'Return';
    return ListTile(
      leading: CircleAvatar(
        backgroundColor: isReturn ? Colors.green.shade100 : Colors.blue.shade100,
        child: Icon(isReturn ? Icons.flag : Icons.car_rental,
          color: isReturn ? Colors.green : Colors.blue)),
      title: Text('${log.logType} — ${log.odometerKm.toStringAsFixed(0)} km'),
      subtitle: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(DateFormatter.format(log.logDate)),
        Text('Fuel: ${log.fuelLevelPct}%'),
        if (isReturn && log.drivenKm != null)
          Text('Driven: ${log.drivenKm!.toStringAsFixed(0)} km'),
      ]),
      trailing: (isReturn && (log.overageCharge ?? 0) > 0)
        ? Text('+${CurrencyFormatter.format(log.overageCharge!)}',
            style: const TextStyle(color: Colors.red, fontWeight: FontWeight.bold))
        : null,
    );
  }
}
```

---

## 8. Vehicle Map Screen (Fleet Manager Only)

```dart
class VehicleMapScreen extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final locations = ref.watch(vehicleLocationsProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Fleet Map')),
      body: locations.when(
        data: (positions) => GoogleMap(
          initialCameraPosition: CameraPosition(
            target: positions.isNotEmpty
                ? LatLng(positions.first.lat, positions.first.lng)
                : const LatLng(25.2048, 55.2708),
            zoom: 10),
          markers: positions.map((p) => Marker(
            markerId: MarkerId(p.assetName),
            position: LatLng(p.lat, p.lng),
            infoWindow: InfoWindow(
              title: p.assetName,
              snippet: '${p.speedKmh} km/h'),
          )).toSet(),
        ),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => ErrorView(message: '$e'),
      ),
    );
  }
}
```

**Route guard** in `app_router.dart`:
```dart
GoRoute(
  path: '/fleet-map',
  redirect: (ctx, _) async =>
      (await AuthService().hasRole('Fleet Manager')) ? null : '/',
  builder: (_, __) => const VehicleMapScreen(),
),
```

---

## 9. API Layer (`core/api/vehicles_api.dart`)

```dart
class VehiclesApi {
  final _client = FrappeClient();

  Future<List<VehicleAsset>> getVehicles(VehicleFilter filter) async {
    final data = await _client.get(
      'rental_core.api.assets.get_available_assets',
      params: {'asset_type': 'Vehicle', ...filter.toMap()},
    );
    return (data['assets'] as List).map(VehicleAsset.fromJson).toList();
  }

  Future<VehicleAsset> getVehicleDetail(String assetName) async {
    final data = await _client.get(
      'rental_vehicles.api.vehicles.get_vehicle_detail',
      params: {'asset_name': assetName},
    );
    return VehicleAsset.fromJson(data as Map<String, dynamic>);
  }

  Future<List<MileageLog>> getMileageLogs(String agreementId) async {
    final data = await _client.get(
      'rental_vehicles.api.vehicles.get_mileage_history',
      params: {'agreement': agreementId},
    );
    return (data as List).map((e) => MileageLog.fromJson(e)).toList();
  }

  Future<void> reportViolation({
    required String agreement,
    required String violationType,
    required double fineAmount,
    required String violationDate,
    required String authority,
    String? evidenceDoc,
  }) async {
    await _client.post(
      'rental_vehicles.api.vehicles.report_traffic_violation',
      body: {
        'agreement': agreement,
        'violation_type': violationType,
        'fine_amount': fineAmount,
        'violation_date': violationDate,
        'authority': authority,
        if (evidenceDoc != null) 'evidence_doc': evidenceDoc,
      },
    );
  }
}
```

---

## 10. Implementation Phases

| Phase | Deliverables |
|---|---|
| **1** | Vehicle catalog + filter sheet, vehicle detail with spec grid + mileage policy card |
| **2** | Booking Step 2 driver license fields with client-side validation |
| **3** | Mileage log screen, traffic violation report screen |
| **4** | Live GPS map (Fleet Manager only), 3D preview WebView |

---

## 11. Testing Checklist

- [ ] Vehicle filter sheet applies all filter dimensions correctly
- [ ] Mileage policy card shows correct values from `VehicleCategory`
- [ ] Driver age below minimum → Step 2 cannot advance; error shown
- [ ] License expiry before rental end → Step 2 cannot advance; error shown
- [ ] Server-side rejects invalid age/license even if client validation is bypassed
- [ ] Mileage log screen shows Pickup and Return entries with overage breakdown
- [ ] Live map route accessible only to Fleet Manager role
- [ ] Traffic violation creates a record in Frappe and appears in violation history
