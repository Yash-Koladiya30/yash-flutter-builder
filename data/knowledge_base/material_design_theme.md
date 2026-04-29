# Material 3 Theming

Every AppAspect app uses Material 3 with a single `ColorScheme.fromSeed` source of truth.

## Theme configuration

```dart
class AppTheme {
  static ThemeData light = ThemeData(
    useMaterial3: true,
    colorScheme: ColorScheme.fromSeed(
      seedColor: Colors.indigo,
      brightness: Brightness.light,
    ),
    appBarTheme: const AppBarTheme(
      elevation: 0,
      centerTitle: false,
    ),
    cardTheme: CardTheme(
      elevation: 1,
      margin: const EdgeInsets.all(12),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
    ),
  );

  static ThemeData dark = ThemeData(
    useMaterial3: true,
    colorScheme: ColorScheme.fromSeed(
      seedColor: Colors.indigo,
      brightness: Brightness.dark,
    ),
  );
}

MaterialApp(theme: AppTheme.light, darkTheme: AppTheme.dark, themeMode: ThemeMode.system);
```

## Rules

- Always `useMaterial3: true`.
- Generate the palette from ONE `seedColor`, never hand-pick 10 hex values.
- Access colors via `Theme.of(context).colorScheme.primary`, never `Colors.blue` inline.
- Set `AppBarTheme.elevation: 0` — Material 3 apps use tonal elevation, not shadows.
- Font sizes via `textTheme.*` (bodyLarge, titleMedium, labelSmall), not hardcoded.
