<script lang="ts">
	import { onMount, onDestroy } from 'svelte';

	// Language options
	const inputLanguages = [
		{ code: null, name: 'Auto-detect', nllbCode: null },
		{ code: 'en', name: 'English', nllbCode: 'english' },
		{ code: 'es', name: 'Spanish', nllbCode: 'spanish' },
		{ code: 'tr', name: 'Turkish', nllbCode: 'turkish' },
		{ code: 'pt', name: 'Portuguese', nllbCode: 'portuguese' },
		{ code: 'ko', name: 'Korean', nllbCode: 'korean' },
		{ code: 'zh', name: 'Chinese', nllbCode: 'mandarin' },
		{ code: 'fa', name: 'Farsi/Persian', nllbCode: 'farsi' },
		{ code: 'ru', name: 'Russian', nllbCode: 'russian' },
		{ code: 'ja', name: 'Japanese', nllbCode: 'japanese' }
	];

	const outputLanguages = [
		{ code: 'spanish', name: 'Spanish' },
		{ code: 'turkish', name: 'Turkish' },
		{ code: 'portuguese', name: 'Portuguese' },
		{ code: 'korean', name: 'Korean' },
		{ code: 'mandarin', name: 'Chinese/Mandarin' },
		{ code: 'farsi', name: 'Farsi/Persian' },
		{ code: 'russian', name: 'Russian' },
		{ code: 'english', name: 'English' },
		{ code: 'japanese', name: 'Japanese' }
	];

	// Font size options for translation display
	const fontSizeOptions = [
		{ value: '2rem', label: 'Small' },
		{ value: '3rem', label: 'Medium' },
		{ value: '4rem', label: 'Large' },
		{ value: '5.5rem', label: 'Extra Large (Default)' },
		{ value: '7rem', label: 'Huge' },
		{ value: '9rem', label: 'Massive' }
	];

	// State variables
	let selectedInputLanguage = null;
	let selectedOutputLanguage = '';
	let selectedFontSize = '5.5rem';
	let isConnected = false;
	let isRunning = false;
	let ws: WebSocket | null = null;
	let transcription = '';
	let translation = '';
	let currentSourceLanguage = '';
	let confidence = 0;
	let translationConfidence = 0;
	let audioLevel = 0;
	let errorMessage = '';
	let connectionStatus = 'Disconnected';
	let currentAudioDevice = 'Not selected';

	// WebSocket connection
	function connectWebSocket() {
		try {
			ws = new WebSocket('ws://127.0.0.1:8000/ws');
			
			ws.onopen = () => {
				isConnected = true;
				connectionStatus = 'Connected';
				errorMessage = '';
			};

			ws.onmessage = (event) => {
				try {
					const message = JSON.parse(event.data);
					
					switch (message.type) {
						case 'transcription':
							transcription = message.data.text;
							currentSourceLanguage = message.data.language;
							confidence = message.data.confidence;
							break;
						
						case 'translation':
							if (message.data.target_language === selectedOutputLanguage) {
								translation = message.data.translated_text;
								translationConfidence = message.data.confidence;
							}
							break;
						
						case 'status':
							isRunning = message.data.is_running;
							audioLevel = message.data.audio_level || 0;
							currentAudioDevice = message.data.audio_device || 'Unknown';
							break;
						
						case 'error':
							errorMessage = message.data.message;
							break;
					}
				} catch (e) {
					console.error('Error parsing WebSocket message:', e);
				}
			};

			ws.onclose = () => {
				isConnected = false;
				connectionStatus = 'Disconnected';
				setTimeout(connectWebSocket, 3000); // Auto-reconnect
			};

			ws.onerror = (error) => {
				console.error('WebSocket error:', error);
				errorMessage = 'WebSocket connection error';
				isConnected = false;
				connectionStatus = 'Error';
			};
		} catch (e) {
			console.error('Failed to connect WebSocket:', e);
			errorMessage = 'Failed to connect to backend';
		}
	}

	// API functions
	async function startPipeline() {
		if (!selectedOutputLanguage) {
			errorMessage = 'Please select an output language';
			return;
		}

		try {
			const response = await fetch('http://127.0.0.1:8000/pipeline/start', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
				},
				body: JSON.stringify({
					source_language: selectedInputLanguage,
					target_languages: [selectedOutputLanguage],
					whisper_model: 'large-v3',
					device_index: null,
					sample_rate: 16000
				})
			});

			if (!response.ok) {
				const error = await response.json();
				throw new Error(error.detail || 'Failed to start pipeline');
			}

			const result = await response.json();
			if (result.success) {
				isRunning = true;
				errorMessage = '';
				transcription = '';
				translation = '';
			} else {
				throw new Error(result.message);
			}
		} catch (e) {
			errorMessage = `Failed to start: ${e.message}`;
		}
	}

	async function stopPipeline() {
		try {
			const response = await fetch('http://127.0.0.1:8000/pipeline/stop', {
				method: 'POST'
			});

			if (!response.ok) {
				const error = await response.json();
				throw new Error(error.detail || 'Failed to stop pipeline');
			}

			isRunning = false;
			errorMessage = '';
		} catch (e) {
			errorMessage = `Failed to stop: ${e.message}`;
		}
	}

	// Lifecycle
	onMount(() => {
		connectWebSocket();
	});

	onDestroy(() => {
		if (ws) {
			ws.close();
		}
	});

	$: canStart = !isRunning && isConnected && selectedOutputLanguage;
	$: canStop = isRunning && isConnected;
</script>

<div class="container">
	<header>
		<h1>🌍 Real-Time Translation</h1>
		<div class="status">
			<span class="connection-status" class:connected={isConnected} class:disconnected={!isConnected}>
				{connectionStatus}
			</span>
		</div>
	</header>

	<div class="controls">
		<div class="language-selectors">
			<div class="selector-group">
				<label for="input-language">Input Language:</label>
				<select id="input-language" bind:value={selectedInputLanguage} disabled={isRunning}>
					{#each inputLanguages as lang}
						<option value={lang.code}>{lang.name}</option>
					{/each}
				</select>
			</div>

			<div class="arrow">→</div>

			<div class="selector-group">
				<label for="output-language">Output Language:</label>
				<select id="output-language" bind:value={selectedOutputLanguage} disabled={isRunning}>
					<option value="">Select output language...</option>
					{#each outputLanguages as lang}
						<option value={lang.code}>{lang.name}</option>
					{/each}
				</select>
			</div>

			<div class="selector-group">
				<label for="font-size">Translation Size:</label>
				<select id="font-size" bind:value={selectedFontSize}>
					{#each fontSizeOptions as size}
						<option value={size.value}>{size.label}</option>
					{/each}
				</select>
			</div>
		</div>

		<div class="audio-device-info">
			<label>🎤 Current Audio Input:</label>
			<span class="device-name">{currentAudioDevice}</span>
		</div>

		<div class="action-buttons">
			{#if canStart}
				<button on:click={startPipeline} class="start-btn">
					🎤 Start Translation
				</button>
			{:else if canStop}
				<button on:click={stopPipeline} class="stop-btn">
					⏹️ Stop Translation
				</button>
			{:else}
				<button disabled>
					{#if !isConnected}
						Connecting...
					{:else if !selectedOutputLanguage}
						Select Languages
					{:else}
						Loading...
					{/if}
				</button>
			{/if}
		</div>
	</div>

	{#if errorMessage}
		<div class="error-message">
			⚠️ {errorMessage}
		</div>
	{/if}


	<div class="translation-display">
		<div class="transcription-panel">
			<h3>
				🎙️ Transcription 
				{#if currentSourceLanguage}
					<span class="language-tag">[{currentSourceLanguage}]</span>
				{/if}
				{#if confidence > 0}
					<span class="confidence">({Math.round(confidence * 100)}%)</span>
				{/if}
			</h3>
			<div class="text-output">
				{transcription || (isRunning ? 'Listening...' : 'Start translation to see transcription')}
			</div>
		</div>

		<div class="translation-panel">
			<h3>
				🌍 Translation 
				{#if selectedOutputLanguage}
					<span class="language-tag">[{outputLanguages.find(l => l.code === selectedOutputLanguage)?.name}]</span>
				{/if}
				{#if translationConfidence > 0}
					<span class="confidence">({Math.round(translationConfidence * 100)}%)</span>
				{/if}
			</h3>
			<div class="text-output translation-text" style="--selected-font-size: {selectedFontSize};">
				{translation || (isRunning && transcription ? 'Translating...' : 'Translation will appear here')}
			</div>
		</div>
	</div>
</div>

<style>
	.container {
		margin: 0 auto;
		padding: 2rem;
		font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
		width: 100%;
		box-sizing: border-box;
	}

	header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 2rem;
		border-bottom: 2px solid #f0f0f0;
		padding-bottom: 1rem;
	}

	h1 {
		color: #333;
		margin: 0;
	}

	.status {
		display: flex;
		align-items: center;
		gap: 1rem;
	}

	.connection-status {
		padding: 0.5rem 1rem;
		border-radius: 20px;
		font-size: 0.9rem;
		font-weight: 500;
	}

	.connected {
		background: #d4edda;
		color: #155724;
		border: 1px solid #c3e6cb;
	}

	.disconnected {
		background: #f8d7da;
		color: #721c24;
		border: 1px solid #f5c6cb;
	}

	.controls {
		background: #f8f9fa;
		padding: 2rem;
		border-radius: 10px;
		margin-bottom: 2rem;
	}

	.language-selectors {
		display: flex;
		align-items: center;
		gap: 2rem;
		margin-bottom: 2rem;
		flex-wrap: wrap;
	}

	.selector-group {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		min-width: 200px;
	}

	.arrow {
		font-size: 2rem;
		color: #6c757d;
		margin-top: 1.5rem;
	}

	label {
		font-weight: 500;
		color: #495057;
	}

	select {
		padding: 0.75rem;
		border: 2px solid #dee2e6;
		border-radius: 5px;
		font-size: 1rem;
		background: white;
	}

	select:focus {
		outline: none;
		border-color: #007bff;
	}

	select:disabled {
		background: #e9ecef;
		color: #6c757d;
	}

	.audio-device-info {
		background: #e9f7ef;
		border: 1px solid #c3e6cb;
		border-radius: 8px;
		padding: 1rem;
		margin-bottom: 1.5rem;
		display: flex;
		align-items: center;
		gap: 1rem;
	}

	.audio-device-info label {
		font-weight: 600;
		color: #155724;
		margin: 0;
	}

	.device-name {
		background: white;
		padding: 0.5rem 1rem;
		border-radius: 20px;
		font-family: monospace;
		font-size: 0.9rem;
		color: #495057;
		border: 1px solid #dee2e6;
		flex: 1;
		text-align: center;
	}

	.action-buttons {
		display: flex;
		justify-content: center;
	}

	button {
		padding: 1rem 2rem;
		font-size: 1.1rem;
		font-weight: 500;
		border: none;
		border-radius: 25px;
		cursor: pointer;
		transition: all 0.3s ease;
	}

	.start-btn {
		background: #28a745;
		color: white;
	}

	.start-btn:hover {
		background: #218838;
		transform: translateY(-2px);
	}

	.stop-btn {
		background: #dc3545;
		color: white;
	}

	.stop-btn:hover {
		background: #c82333;
		transform: translateY(-2px);
	}

	button:disabled {
		background: #6c757d;
		color: white;
		cursor: not-allowed;
		transform: none;
	}

	.error-message {
		background: #f8d7da;
		color: #721c24;
		padding: 1rem;
		border: 1px solid #f5c6cb;
		border-radius: 5px;
		margin-bottom: 1rem;
	}


	.translation-display {
		display: flex;
		flex-direction: column;
		gap: 2rem;
	}

	.transcription-panel,
	.translation-panel {
		background: white;
		border: 2px solid #dee2e6;
		border-radius: 10px;
		padding: 1.5rem;
		min-height: 200px;
	}

	.transcription-panel h3,
	.translation-panel h3 {
		margin: 0 0 1rem 0;
		color: #495057;
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.language-tag {
		background: #007bff;
		color: white;
		padding: 0.2rem 0.5rem;
		border-radius: 12px;
		font-size: 0.8rem;
	}

	.confidence {
		background: #6c757d;
		color: white;
		padding: 0.2rem 0.5rem;
		border-radius: 12px;
		font-size: 0.8rem;
	}

	.text-output {
		background: #f8f9fa;
		padding: 1rem;
		border-radius: 5px;
		min-height: 100px;
		line-height: 1.6;
		font-size: 1.1rem;
		border-left: 4px solid #007bff;
	}

	.translation-panel .text-output {
		border-left-color: #28a745;
		line-height: 1.2;
		font-weight: 600;
		text-align: center;
		min-height: 300px;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: var(--selected-font-size, 5.5rem);
	}

	@media (max-width: 768px) {
		.language-selectors {
			flex-direction: column;
			align-items: stretch;
		}

		.arrow {
			text-align: center;
			margin: 0;
		}

		.translation-panel .text-output {
			min-height: 200px;
		}

		.audio-device-info {
			flex-direction: column;
			align-items: stretch;
			gap: 0.5rem;
		}

		.audio-device-info label {
			text-align: center;
		}

		.container {
			padding: 1rem;
		}
	}
</style>
