# Form Handling

Every form uses `Form` + `GlobalKey<FormState>` + `TextFormField`. Validation happens on submit.

## Full example

```dart
class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  void _submit() {
    if (!_formKey.currentState!.validate()) return;
    context.read<AuthBloc>().add(
      LoginRequested(email: _emailController.text, password: _passwordController.text),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Sign in')),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                TextFormField(
                  controller: _emailController,
                  keyboardType: TextInputType.emailAddress,
                  decoration: const InputDecoration(labelText: 'Email'),
                  validator: (v) {
                    if (v == null || v.isEmpty) return 'Email is required';
                    if (!v.contains('@')) return 'Enter a valid email';
                    return null;
                  },
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _passwordController,
                  obscureText: true,
                  decoration: const InputDecoration(labelText: 'Password'),
                  validator: (v) {
                    if (v == null || v.length < 6) return 'At least 6 characters';
                    return null;
                  },
                ),
                const SizedBox(height: 24),
                FilledButton(onPressed: _submit, child: const Text('Sign in')),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
```

## Rules

- **Always dispose** `TextEditingController`s in `dispose()`.
- Run `.validate()` before reading values — it triggers all validators and shows errors.
- Use `keyboardType` for email/number/phone to help the user.
- Use `obscureText: true` for passwords.
- Label every field with `InputDecoration(labelText: ...)` — helpful for accessibility and clear UX.
- Never put business logic in validators — just format checks. API-level errors come back via BLoC.
