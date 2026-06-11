# Base — Flutter: Technical Document

> **Product**: Asset Rental Platform
> **Module**: Customer Mobile App (Base Layer)
> **Document Type**: Technical
> **Audience**: Flutter developers
> **Companion**: [[../Base Overview|Base Platform Overview]]

---

## 1. Project Setup

```bash
flutter create --org com.yourorg --platforms android,ios rental_app
cd rental_app
```

### `pubspec.yaml` — Key Dependencies

```yaml
dependencies:
  flutter: { sdk: flutter }
  dio: ^5.4.0                       # HTTP client
  go_router: ^13.0.0                # Declarative routing
  flutter_riverpod: ^2.5.0          # State management
  riverpod_annotation: ^2.3.0
  flutter_secure_storage: ^9.0.0    # Credential keychain
  firebase_core: ^2.27.0
  firebase_messaging: ^14.7.0       # FCM push
  signature: ^5.3.0                 # Canvas signature pad
  cached_network_image: ^3.3.0      # Image caching
  intl: ^0.19.0
  flutter_pdfview: ^1.3.2           # Agreement PDF viewer
  webview_flutter: ^4.7.0           # Payment gateway WebView
  image_picker: ^1.0.7              # KYC photo / file upload
  table_calendar: ^3.1.1            # Availability calendar
  shimmer: ^3.0.0                   # Loading skeleton UI
  freezed_annotation: ^2.4.0        # Immutable models
  fl_chart: ^0.67.0                 # Utility charts (used by flat module)
  connectivity_plus: ^6.0.0         # Network state detection

dev_dependencies:
  build_runner: ^2.4.0
  freezed: ^2.4.0
  riverpod_generator: ^2.3.0
  mocktail: ^1.0.0                  # Mocking for tests
```

---

## 2. Project Structure

> [!NOTE]
> All modules use **domain-specific names**. No `utils/` or `shared/utils/` directories — formatters live under `core/formatting/`, and shared widgets are explicitly named.

```
lib/
├── main.dart
├── app/
│   ├── app.dart                    # MaterialApp + GoRouter + theme
│   ├── config.dart                 # Per-client compile-time config
│   ├── theme/
│   │   ├── app_theme.dart
│   │   ├── colors.dart
│   │   └── typography.dart
│   └── router/
│       └── app_router.dart
├── core/
│   ├── api/
│   │   ├── frappe_client.dart      # Dio provider with auth interceptor
│   │   ├── assets_api.dart
│   │   ├── agreements_api.dart
│   │   ├── payments_api.dart
│   │   └── notifications_api.dart
│   ├── models/
│   │   ├── rental_asset.dart
│   │   ├── rental_agreement.dart
│   │   ├── invoice.dart
│   │   ├── api_error.dart          # Typed error envelope model
│   │   └── notification_item.dart
│   ├── services/
│   │   ├── auth_notifier.dart      # Riverpod AsyncNotifier for auth state
│   │   ├── fcm_service.dart
│   │   └── secure_storage_provider.dart  # Single DI point for FlutterSecureStorage
│   └── formatting/
│       ├── date_formatter.dart     # Domain-specific date display helpers
│       └── currency_formatter.dart # Region-aware currency formatting
├── features/
│   ├── auth/
│   │   ├── login_screen.dart
│   │   ├── register_screen.dart
│   │   └── kyc_upload_screen.dart
│   ├── home/
│   │   └── home_screen.dart
│   ├── catalog/
│   │   ├── catalog_screen.dart
│   │   ├── asset_card_widget.dart
│   │   └── filter_sheet.dart
│   ├── asset_detail/
│   │   ├── asset_detail_screen.dart
│   │   ├── photo_gallery_widget.dart
│   │   ├── availability_calendar_widget.dart
│   │   └── preview_3d_screen.dart
│   ├── booking/
│   │   ├── booking_flow_screen.dart
│   │   ├── booking_outbox.dart     # Offline booking persistence + retry
│   │   ├── steps/
│   │   │   ├── step_dates.dart
│   │   │   ├── step_details.dart
│   │   │   ├── step_kyc.dart
│   │   │   ├── step_signature.dart
│   │   │   └── step_confirm.dart
│   │   └── signature_pad_widget.dart
│   ├── my_rentals/
│   │   ├── my_rentals_screen.dart
│   │   └── agreement_detail_screen.dart
│   ├── payments/
│   │   ├── invoices_screen.dart
│   │   ├── pay_screen.dart
│   │   └── receipt_screen.dart
│   ├── notifications/
│   │   └── notifications_screen.dart
│   └── profile/
│       ├── profile_screen.dart
│       └── documents_screen.dart
└── widgets/
    ├── app_button.dart
    ├── app_card.dart
    ├── status_badge.dart
    ├── loading_overlay.dart
    ├── offline_banner.dart          # Persistent "No connection" indicator
    └── error_view.dart
```

---

## 3. Per-Client Build Configuration (`app/config.dart`)

```dart
class AppConfig {
  static const baseUrl    = String.fromEnvironment('BASE_URL',
      defaultValue: 'https://demo.rentalplatform.com');
  static const brandColor = Color(
      int.fromEnvironment('BRAND_COLOR', defaultValue: 0xFF2563EB));
  static const appName    = String.fromEnvironment('APP_NAME',
      defaultValue: 'Rental Platform');
  static const logoAsset  = String.fromEnvironment('LOGO_ASSET',
      defaultValue: 'assets/logo.png');
  static const hasFlats   = bool.fromEnvironment('HAS_FLATS',   defaultValue: true);
  static const hasVehicles = bool.fromEnvironment('HAS_VEHICLES', defaultValue: true);
}
```

**Build command per client:**
```bash
flutter build apk \
  --dart-define=BASE_URL=https://client1.example.com \
  --dart-define=BRAND_COLOR=0xFF1A73E8 \
  --dart-define=APP_NAME=ClientOne+Rentals \
  --dart-define=HAS_FLATS=true \
  --dart-define=HAS_VEHICLES=false
```

---

## 4. Secure Storage Provider (`core/services/secure_storage_provider.dart`)

> [!NOTE]
> A single Riverpod provider for `FlutterSecureStorage`, injected into all services that need it. This enables test mocking via `ProviderScope(overrides: [...])`.

```dart
@riverpod
FlutterSecureStorage secureStorage(Ref ref) {
  return const FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
    iOptions: IOSOptions(accessibility: KeychainAccessibility.first_unlock),
  );
}
```

---

## 5. `FrappeClient` — Dio Provider

> [!IMPORTANT]
> `FrappeClient` is provided via Riverpod (not a hard singleton). This makes it testable — tests can override it with a mock Dio instance via `ProviderScope(overrides: [...])`.

```dart
// core/api/frappe_client.dart
@riverpod
FrappeClient frappeClient(Ref ref) {
  final storage = ref.read(secureStorageProvider);
  final client = FrappeClient(storage);
  client.init(AppConfig.baseUrl);
  return client;
}

class FrappeClient {
  final FlutterSecureStorage _storage;

  FrappeClient(this._storage);

  late final Dio _dio;

  void init(String baseUrl) {
    _dio = Dio(BaseOptions(
      baseUrl: baseUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 20),
      headers: {'Accept': 'application/json'},
    ));
    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (opts, handler) async {
        final key    = await _storage.read(key: 'api_key');
        final secret = await _storage.read(key: 'api_secret');
        if (key != null) opts.headers['Authorization'] = 'token $key:$secret';
        handler.next(opts);
      },
      onError: (err, handler) {
        if (err.response?.statusCode == 401) {
          // Emit unauthenticated event → router redirects to /login
          authStateController.add(AuthState.unauthenticated);
        }
        handler.next(err);
      },
    ));
  }

  Future<dynamic> get(String method, {Map<String, dynamic>? params}) async {
    final r = await _dio.get('/api/method/$method', queryParameters: params);
    return r.data['message'];
  }

  Future<dynamic> post(String method, {Map<String, dynamic>? body}) async {
    final r = await _dio.post('/api/method/$method', data: body);
    return r.data['message'];
  }
}
```

### TLS & Transport Security

> [!IMPORTANT]
> - The app must **only connect over HTTPS**. `BaseOptions.baseUrl` must start with `https://`.
> - For production builds, consider **certificate pinning** using `dio_http2_adapter` or a custom `SecurityContext` to prevent MITM attacks.
> - API keys are transmitted on every request as `token key:secret` — TLS is the only protection in transit.
> - For future hardening: migrate to OAuth2 with refresh tokens via `frappe.integrations.oauth2`. This adds token expiry (limiting damage from credential leaks) and eliminates the need to store long-lived secrets on-device.

---

## 6. Auth Notifier (`core/services/auth_notifier.dart`)

> [!NOTE]
> Auth state is managed as a Riverpod `AsyncNotifier`, making login/logout reactive across the entire widget tree. No raw `StreamController` is needed.

```dart
enum AuthState { authenticated, unauthenticated, loading }

@riverpod
class AuthNotifier extends _$AuthNotifier {
  @override
  Future<AuthState> build() async {
    final storage = ref.read(secureStorageProvider);
    final hasKey = await storage.read(key: 'api_key') != null;
    return hasKey ? AuthState.authenticated : AuthState.unauthenticated;
  }

  Future<bool> login(String email, String password) async {
    state = const AsyncLoading();
    try {
      final client = ref.read(frappeClientProvider);
      final resp = await client.post(
        'frappe.core.doctype.user.user.login',
        body: {'usr': email, 'pwd': password},
      );
      final storage = ref.read(secureStorageProvider);
      await storage.write(key: 'api_key',    value: resp['api_key']);
      await storage.write(key: 'api_secret', value: resp['api_secret']);
      await storage.write(key: 'user_email', value: email);
      await FcmService(ref).registerToken();
      state = const AsyncData(AuthState.authenticated);
      return true;
    } catch (e) {
      state = AsyncError(e, StackTrace.current);
      return false;
    }
  }

  Future<void> logout() async {
    final storage = ref.read(secureStorageProvider);
    final client = ref.read(frappeClientProvider);
    await FcmService(ref).deregisterToken();
    await client.post('logout');
    await storage.deleteAll();
    state = const AsyncData(AuthState.unauthenticated);
  }
}
```

---

## 7. GoRouter Configuration (`app/router/app_router.dart`)

```dart
final router = GoRouter(
  redirect: (context, state) async {
    final auth = ref.read(authNotifierProvider);
    final isLoggedIn = auth.valueOrNull == AuthState.authenticated;
    final guarded  = ['/book', '/my-rentals', '/invoices', '/pay', '/documents'];
    final isGuarded = guarded.any((p) => state.uri.path.startsWith(p));
    if (!isLoggedIn && isGuarded) return '/login?from=${state.uri.path}';
    return null;
  },
  routes: [
    GoRoute(path: '/',           builder: (_, __) => const HomeScreen()),
    GoRoute(path: '/catalog',    builder: (_, __) => const CatalogScreen()),
    GoRoute(path: '/asset/:id',  builder: (_, s)  =>
        AssetDetailScreen(assetId: s.pathParameters['id']!)),
    GoRoute(path: '/book/:id',   builder: (_, s)  =>
        BookingFlowScreen(assetId: s.pathParameters['id']!)),
    GoRoute(path: '/my-rentals', builder: (_, __) => const MyRentalsScreen()),
    GoRoute(path: '/agreement/:id', builder: (_, s) =>
        AgreementDetailScreen(agreementId: s.pathParameters['id']!)),
    GoRoute(path: '/invoices',   builder: (_, __) => const InvoicesScreen()),
    GoRoute(path: '/pay/:id',    builder: (_, s)  =>
        PayScreen(invoiceId: s.pathParameters['id']!)),
    GoRoute(path: '/notifications', builder: (_, __) => const NotificationsScreen()),
    GoRoute(path: '/profile',    builder: (_, __) => const ProfileScreen()),
    GoRoute(path: '/documents',  builder: (_, __) => const DocumentsScreen()),
    GoRoute(path: '/login',      builder: (_, __) => const LoginScreen()),
    GoRoute(path: '/register',   builder: (_, __) => const RegisterScreen()),
  ],
);
```

---

## 8. Riverpod Providers (Key Patterns)

```dart
// Parameterized asset catalog
@riverpod
Future<List<RentalAsset>> availableAssets(Ref ref, AssetFilter filter) =>
    ref.read(frappeClientProvider).get(
      'rental_core.api.assets.get_available_assets',
      params: filter.toMap(),
    ).then((data) => (data['assets'] as List).map(RentalAsset.fromJson).toList());

// Customer's agreements
@riverpod
Future<List<RentalAgreement>> myAgreements(Ref ref) =>
    ref.read(frappeClientProvider).get(
      'rental_core.api.agreements.get_my_agreements',
    ).then((data) => (data as List).map(RentalAgreement.fromJson).toList());

// Booking flow state (Notifier)
@riverpod
class BookingNotifier extends _$BookingNotifier {
  @override
  BookingState build() => const BookingState();

  void setDates(DateTime start, int months) =>
      state = state.copyWith(startDate: start, durationMonths: months);

  void setPersonalDetails(String name, String phone) =>
      state = state.copyWith(fullName: name, phone: phone);

  void setSignature(String base64) =>
      state = state.copyWith(signatureData: base64);

  Future<String?> submit() async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final client = ref.read(frappeClientProvider);
      final result = await client.post(
        'rental_core.api.bookings.submit_booking_request',
        body: state.toApiPayload(),
      );
      state = state.copyWith(isLoading: false, agreementName: result['agreement_name']);
      return result['payment_url'];
    } on DioException catch (e) {
      if (e.type == DioExceptionType.connectionError) {
        // Save to outbox for retry when back online
        await ref.read(bookingOutboxProvider.notifier).enqueue(state);
        state = state.copyWith(isLoading: false, savedOffline: true);
        return null;
      }
      state = state.copyWith(isLoading: false, error: e.toString());
      return null;
    }
  }
}
```

---

## 9. Booking Outbox — Offline Persistence (`features/booking/booking_outbox.dart`)

> [!IMPORTANT]
> The functional requirements state: "booking is not silently lost" if the device is offline. This outbox pattern serializes the booking request to local storage and retries when connectivity is restored.

```dart
@riverpod
class BookingOutbox extends _$BookingOutbox {
  @override
  List<BookingState> build() => _loadFromDisk();

  Future<void> enqueue(BookingState booking) async {
    state = [...state, booking];
    await _persistToDisk(state);
  }

  Future<void> retryAll() async {
    final client = ref.read(frappeClientProvider);
    final remaining = <BookingState>[];
    for (final booking in state) {
      try {
        await client.post(
          'rental_core.api.bookings.submit_booking_request',
          body: booking.toApiPayload(),
        );
        // Success — don't add to remaining
      } catch (_) {
        remaining.add(booking);
      }
    }
    state = remaining;
    await _persistToDisk(state);
  }

  List<BookingState> _loadFromDisk() {
    // SharedPreferences JSON deserialization
    return [];
  }

  Future<void> _persistToDisk(List<BookingState> bookings) async {
    // SharedPreferences JSON serialization
  }
}

// Connectivity listener — triggers retry when back online
@riverpod
void connectivityWatcher(Ref ref) {
  Connectivity().onConnectivityChanged.listen((result) {
    if (result != ConnectivityResult.none) {
      final outbox = ref.read(bookingOutboxProvider);
      if (outbox.isNotEmpty) {
        ref.read(bookingOutboxProvider.notifier).retryAll();
      }
    }
  });
}
```

---

## 10. FCM Push Notifications (`core/services/fcm_service.dart`)

```dart
class FcmService {
  final Ref _ref;
  FcmService(this._ref);

  Future<void> registerToken() async {
    await Firebase.initializeApp();
    final messaging = FirebaseMessaging.instance;
    await messaging.requestPermission();
    final token = await messaging.getToken();
    if (token != null) {
      await _ref.read(frappeClientProvider).post(
        'rental_core.api.notifications.register_push_token',
        body: {'token': token},
      );
    }
    // Foreground: show in-app overlay
    FirebaseMessaging.onMessage.listen(_handleForeground);
    // Background tap: navigate to relevant screen
    FirebaseMessaging.onMessageOpenedApp.listen(_handleTap);
  }

  Future<void> deregisterToken() async {
    final token = await FirebaseMessaging.instance.getToken();
    if (token != null) {
      await _ref.read(frappeClientProvider).post(
        'rental_core.api.notifications.deregister_push_token',
        body: {'token': token},
      );
    }
    await FirebaseMessaging.instance.deleteToken();
  }

  void _handleTap(RemoteMessage msg) {
    final type = msg.data['type'];
    if (type == 'invoice')   router.go('/invoices');
    if (type == 'agreement') router.go('/my-rentals');
    if (type == 'renewal')   router.go('/my-rentals');
  }
}
```

---

## 11. API Error Handling (`core/models/api_error.dart`)

> [!NOTE]
> Matches the error envelope contract defined in the Frappe Technical doc (§ 12.2). All API responses are parsed through this model so error handling is consistent.

```dart
@freezed
class ApiError with _$ApiError {
  const factory ApiError({
    required String excType,
    required List<FieldError> errors,
    @Default([]) List<String> serverMessages,
  }) = _ApiError;

  factory ApiError.fromResponse(Response response) {
    final data = response.data;
    return ApiError(
      excType: data['exc_type'] ?? 'UnknownError',
      errors: (data['errors'] as List? ?? [])
          .map((e) => FieldError(field: e['field'], message: e['message']))
          .toList(),
      serverMessages: (data['_server_messages'] as List? ?? [])
          .map((m) => m.toString())
          .toList(),
    );
  }

  String get displayMessage =>
      errors.isNotEmpty ? errors.first.message : 'An unexpected error occurred';
}

@freezed
class FieldError with _$FieldError {
  const factory FieldError({required String field, required String message}) = _FieldError;
}
```

---

## 12. Availability Calendar Widget

```dart
class AvailabilityCalendarWidget extends ConsumerWidget {
  final String assetName;
  const AvailabilityCalendarWidget({required this.assetName, super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final now = DateTime.now();
    final avail = ref.watch(availabilityProvider(
      AvailabilityParams(assetName: assetName, year: now.year, month: now.month),
    ));
    return avail.when(
      data: (data) => TableCalendar(
        firstDay: now,
        lastDay: now.add(const Duration(days: 365)),
        focusedDay: now,
        enabledDayPredicate: (day) => !data.isBlocked(day),
        onPageChanged: (focused) => ref.invalidate(availabilityProvider(
          AvailabilityParams(assetName: assetName, year: focused.year, month: focused.month),
        )),
      ),
      loading: () => const SizedBox(height: 300, child: Center(child: CircularProgressIndicator())),
      error: (e, _) => ErrorView(message: '$e'),
    );
  }
}
```

---

## 13. Offline Caching Strategy

| Data | Strategy |
|---|---|
| Asset catalog | `keepAlive: true` on provider; stale-while-revalidate on screen focus |
| Asset detail | Cached by `assetId`; invalidated on pull-to-refresh |
| Agreements | Cached; `ref.invalidate()` on screen focus |
| Invoices | Always fresh; no caching |
| Notifications | Stored locally (SharedPreferences) on receive |
| Booking submit | **Outbox pattern**: serialized to local storage on connectivity failure, retried automatically when online (see § 9) |

---

## 14. Testing Checklist

- [ ] Login stores API key/secret in secure storage; logout clears all
- [ ] Guarded routes redirect to `/login?from=...`; return after successful login
- [ ] Catalog loads and paginates correctly with `total`, `has_next` metadata
- [ ] Blocked calendar dates are non-tappable; no reason disclosed
- [ ] Booking form validates each step before advancing
- [ ] Signature pad produces non-empty base64 on submit
- [ ] FCM token registered after login; deregistered on logout
- [ ] Push notification tap navigates to correct screen
- [ ] Pay screen opens correct gateway URL in sandboxed WebView
- [ ] `--dart-define` values correctly override app name and brand colour
- [ ] `FrappeClient` can be overridden in tests via `ProviderScope(overrides: [...])`
- [ ] `AuthNotifier` transitions correctly between `authenticated` and `unauthenticated`
- [ ] Booking submitted while offline is saved to outbox and retried on reconnect
- [ ] Offline banner appears when `ConnectivityResult.none` is detected
- [ ] `ApiError` model correctly parses error envelope from 400/409 responses
- [ ] `FlutterSecureStorage` is injected via provider, not instantiated directly
