
        let selectedVoice = 'andrew';
        let currentRateStr = '+1%';
        let pollInterval = null;
        let lastBreakdownData = [];

        function toggleTheme() {
            const html = document.documentElement;
            const currentTheme = html.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            html.setAttribute('data-theme', newTheme);

            const themeIcon = document.getElementById('themeIcon');
            const themeText = document.getElementById('themeText');

            if (newTheme === 'light') {
                themeIcon.textContent = '🌙';
                themeText.textContent = 'Dark';
            } else {
                themeIcon.textContent = '☀️';
                themeText.textContent = 'Light';
            }
        }

        function selectVoice(voice, element) {
            selectedVoice = voice;
            document.querySelectorAll('.voice-item').forEach(el => el.classList.remove('selected'));
            element.classList.add('selected');
        }

        function updateRateLabel(val) {
            const num = parseInt(val);
            const sign = num >= 0 ? '+' : '';
            currentRateStr = `${sign}${num}%`;
            document.getElementById('rateVal').textContent = `${currentRateStr} ${num === 1 ? '(Optimal)' : ''}`;
        }

        function updateWordCount() {
            const scriptInput = document.getElementById('scriptText');
            const wordCountEl = document.getElementById('wordCount');
            const estTimeEl = document.getElementById('estTime');
            if (!scriptInput) return;
            const text = scriptInput.value.trim();
            const words = text ? text.split(/\s+/).filter(Boolean).length : 0;
            const minutes = Math.ceil(words / 150);
            if (wordCountEl) wordCountEl.textContent = `${words.toLocaleString()} Words`;
            if (estTimeEl) estTimeEl.textContent = `~${minutes} min audio`;
        }

        document.addEventListener('DOMContentLoaded', () => {
            const scriptInput = document.getElementById('scriptText');
            if (scriptInput) {
                ['input', 'change', 'paste', 'keyup', 'blur'].forEach(evt => {
                    scriptInput.addEventListener(evt, () => setTimeout(updateWordCount, 10));
                });
                updateWordCount();
            }
        });
        window.addEventListener('load', updateWordCount);

        function escapeHtml(str) {
            if (!str) return '';
            return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
        }

        function copyAllPromptsOnly() {
            if (!lastBreakdownData || !lastBreakdownData.length) {
                alert('No prompts available to copy.');
                return;
            }
            const rawPromptsStr = lastBreakdownData
                .map((item, idx) => {
                    let cleanPrompt = (item.prompt || '').replace(/[\r\n]+/g, ' ').replace(/\s+/g, ' ').trim();
                    return cleanPrompt ? `${idx + 1}. ${cleanPrompt}` : '';
                })
                .filter(p => p.length > 0)
                .join('\n\n');

            navigator.clipboard.writeText(rawPromptsStr).then(() => {
                alert(`Copied ${lastBreakdownData.length} formatted prompts to clipboard! 📋`);
            }).catch(err => {
                const textArea = document.createElement('textarea');
                textArea.value = rawPromptsStr;
                document.body.appendChild(textArea);
                textArea.select();
                document.execCommand('copy');
                document.body.removeChild(textArea);
                alert(`Copied ${lastBreakdownData.length} formatted prompts to clipboard! 📋`);
            });
        }

        function downloadWordDoc() {
            if (!lastBreakdownData || !lastBreakdownData.length) {
                alert('No breakdown data available to download.');
                return;
            }

            const filenameInput = document.getElementById('filenameInput').value.trim();
            const baseTitle = filenameInput ? filenameInput.replace(/\.[^/.]+$/, "") : "script_beat_breakdown";
            const docFilename = `${baseTitle}_prompts.doc`;

            let htmlContent = `
            <html xmlns:o='urn:schemas-microsoft-com:office:office' xmlns:w='urn:schemas-microsoft-com:office:word' xmlns='http://www.w3.org/TR/REC-html40'>
            <head>
                <meta charset='utf-8'>
                <title>Script & Beat Prompts Breakdown</title>
                <style>
                    body { font-family: 'Segoe UI', Arial, sans-serif; margin: 40px; color: #111111; line-height: 1.5; }
                    h1 { color: #0071e3; font-size: 20pt; font-weight: bold; border-bottom: 2px solid #0071e3; padding-bottom: 8px; margin-bottom: 24px; }
                    .beat-card { margin-bottom: 26px; border: 1px solid #d1d1d6; padding: 16px; border-radius: 8px; background: #fafafa; }
                    .beat-title { font-size: 14pt; font-weight: bold; color: #0071e3; margin-bottom: 8px; }
                    .section-label { font-size: 10pt; font-weight: bold; color: #6e6e73; text-transform: uppercase; margin-top: 10px; margin-bottom: 4px; }
                    .script-line { font-size: 11pt; font-weight: bold; color: #1d1d1f; background: #eef2ff; padding: 10px 14px; border-left: 4px solid #0071e3; margin-bottom: 10px; }
                    .prompt-content { font-family: 'Courier New', monospace; font-size: 10pt; color: #1c1c1e; background: #f2f2f7; padding: 12px 14px; border: 1px solid #c7c7cc; white-space: pre-wrap; word-break: break-word; }
                </style>
            </head>
            <body>
                <h1>YouTube Script & 2D Vector Prompt Breakdown</h1>
            `;

            lastBreakdownData.forEach(item => {
                htmlContent += `
                <div class="beat-card">
                    <div class="beat-title"># Beat ${item.scene} (${item.timestamp})</div>
                    
                    <div class="section-label">### Script line:</div>
                    <div class="script-line">"${escapeHtml(item.text)}"</div>
                    
                    <div class="section-label">### Image Prompt:</div>
                    <div class="prompt-content">${escapeHtml(item.prompt)}</div>
                </div>
                `;
            });

            htmlContent += `</body></html>`;

            const blob = new Blob(['\ufeff', htmlContent], {
                type: 'application/msword'
            });

            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = docFilename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }

        let jobStartTime = null;
        let pollErrorCount = 0;

        async function startPollingJob(jobId) {
            if (pollInterval) clearInterval(pollInterval);
            jobStartTime = Date.now();
            pollErrorCount = 0;
            
            const progressBox = document.getElementById('progressBox');
            const progressPercent = document.getElementById('progressPercent');
            const progressBarFill = document.getElementById('progressBarFill');
            const progressStatus = document.getElementById('progressStatus');

            const videoProgressBox = document.getElementById('videoProgressBox');
            const videoProgressPercent = document.getElementById('videoProgressPercent');
            const videoProgressBarFill = document.getElementById('videoProgressBarFill');
            const videoProgressStatus = document.getElementById('videoProgressStatus');
            
            const audioCard = document.getElementById('audioCard');
            const srtCard = document.getElementById('srtCard');
            const breakdownCard = document.getElementById('breakdownCard');

            if (progressBox) progressBox.classList.add('active');

            pollInterval = setInterval(async () => {
                try {
                    const res = await fetch(`/api/job-status?id=${jobId}`);
                    if (!res.ok) {
                        pollErrorCount++;
                        if (pollErrorCount >= 3) {
                            clearInterval(pollInterval);
                            localStorage.removeItem('active_job_id');
                            if (progressBox) progressBox.classList.remove('active');
                            if (videoProgressBox) videoProgressBox.classList.remove('active');
                        }
                        return;
                    }
                    
                    const data = await res.json();
                    if (data.error) {
                        clearInterval(pollInterval);
                        localStorage.removeItem('active_job_id');
                        if (progressBox) progressBox.classList.remove('active');
                        if (videoProgressBox) videoProgressBox.classList.remove('active');
                        return;
                    }
                    pollErrorCount = 0;
                    
                    if (data.progress !== undefined) {
                        progressBarFill.style.width = `${data.progress}%`;
                        if (videoProgressBarFill) videoProgressBarFill.style.width = `${data.progress}%`;

                        let pctText = `${data.progress}%`;
                        if (data.progress > 5 && data.progress < 100 && jobStartTime) {
                            const elapsedSec = (Date.now() - jobStartTime) / 1000;
                            const estTotalSec = elapsedSec / (data.progress / 100);
                            const remSec = Math.max(1, Math.round(estTotalSec - elapsedSec));
                            const min = Math.floor(remSec / 60);
                            const sec = remSec % 60;
                            const timeStr = min > 0 ? `${min}m ${sec}s` : `${sec}s`;
                            pctText = `${data.progress}% (~${timeStr} left)`;
                        }
                        progressPercent.textContent = pctText;
                        if (videoProgressPercent) videoProgressPercent.textContent = pctText;
                    }

                    if (data.status_text) {
                        progressStatus.textContent = data.status_text;
                        if (videoProgressStatus) videoProgressStatus.textContent = data.status_text;

                        const match = data.status_text.match(/Mini-Clip (\d+)\/(\d+)/);
                        if (match) {
                            const activeBeat = parseInt(match[1]);
                            const totalBeats = parseInt(match[2]);
                            for (let b = 1; b <= totalBeats; b++) {
                                const statusBox = document.getElementById(`beatStatusBox_${b}`);
                                const progressEl = document.getElementById(`beatProgress_${b}`);
                                const playerEl = document.getElementById(`beatPlayer_${b}`);
                                if (statusBox) {
                                    if (b === activeBeat) {
                                        statusBox.style.display = 'block';
                                        if (progressEl) progressEl.style.display = 'block';
                                        if (playerEl) playerEl.style.display = 'none';
                                    } else if (b < activeBeat) {
                                        statusBox.style.display = 'block';
                                        if (progressEl) progressEl.style.display = 'none';
                                        if (playerEl) playerEl.style.display = 'block';
                                    }
                                }
                            }
                        }
                    }

                    if (data.status === 'completed') {
                        clearInterval(pollInterval);
                        localStorage.removeItem('active_job_id');
                        progressBox.classList.remove('active');
                        if (videoProgressBox) videoProgressBox.classList.remove('active');

                        const renderBtn = document.getElementById('renderVideoBtn');
                        if (renderBtn) {
                            renderBtn.disabled = false;
                            renderBtn.innerHTML = '⚡ Render 1080p MP4 Video';
                        }

                        if (data.mode === 'audio' && data.result) {
                            const audioElement = document.getElementById('audioElement');
                            const downloadAudioLink = document.getElementById('downloadAudioLink');

                            audioElement.src = data.result.audioUrl;
                            downloadAudioLink.href = data.result.audioUrl;
                            downloadAudioLink.download = data.result.filename;

                            audioCard.classList.add('active');
                            audioElement.play();
                        } else if (data.mode === 'srt' && data.result) {
                            const downloadSrtLink = document.getElementById('downloadSrtLink');

                            downloadSrtLink.href = data.result.srtUrl;
                            downloadSrtLink.download = data.result.srtFilename;

                            srtCard.classList.add('active');
                        } else if (data.mode === 'breakdown' && data.result) {
                            const container = document.getElementById('breakdownContainer');
                            container.innerHTML = '';
                            lastBreakdownData = data.result.scenes;
                            localStorage.setItem('last_active_job_id', jobId);
                            perBeatImages = {};

                            const totalCount = data.result.scenes ? data.result.scenes.length : 0;
                            const badgeEl = document.getElementById('totalScenesBadge');
                            const boldTextEl = document.getElementById('totalScenesBoldText');
                            if (badgeEl && boldTextEl) {
                                boldTextEl.textContent = `${totalCount} Scenes Detected`;
                                badgeEl.style.display = 'inline-flex';
                            }

                            data.result.scenes.forEach(item => {
                                const card = document.createElement('div');
                                card.className = 'breakdown-card';
                                card.innerHTML = `
                                    <div style="font-size:1rem; font-weight:800; color:var(--accent-apple); margin-bottom:8px;"># Beat ${item.scene} <span style="font-size:0.75rem; font-weight:400; color:var(--text-secondary);">• ${item.timestamp}</span></div>
                                    <div style="font-weight:700; font-size:0.78rem; color:var(--text-secondary); margin-top:6px;">### Script line:</div>
                                    <div class="breakdown-script">"${item.text}"</div>
                                    <div style="font-weight:700; font-size:0.78rem; color:var(--text-secondary); margin-top:6px;">### Image Prompt:</div>
                                    <div class="breakdown-prompt" style="white-space:pre-wrap; font-family:monospace;">${item.prompt}</div>

                                    <!-- Per-Beat 3-Button Action Suite -->
                                    <div style="margin-top:14px; padding:12px; background:var(--bg-input); border:1px solid var(--border-subtle); border-radius:12px; display:flex; flex-direction:column; gap:10px;">
                                        <!-- Button 1: Upload Image -->
                                        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                                            <label style="font-size:0.78rem; font-weight:700; color:var(--text-primary);">📷 Step 1: Upload Image</label>
                                            <input type="file" accept="image/*" style="font-size:0.75rem; color:var(--text-primary);" onchange="handlePerBeatImageUpload(${item.scene}, this)" />
                                        </div>
                                        <div id="beatPreview_${item.scene}" style="display:none; margin-top:4px;">
                                            <img id="beatImg_${item.scene}" style="max-height:120px; border-radius:8px; border:1px solid var(--border-subtle); display:block; margin-bottom:4px;" />
                                            <span style="font-size:0.72rem; color:#34c759; font-weight:700;">✓ Image Loaded for Beat #${item.scene}</span>
                                        </div>

                                        <!-- Buttons 2 & 3 Grid -->
                                        <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-top:4px;">
                                            <button id="btnBeatAudio_${item.scene}" class="btn-apple btn-apple-secondary" style="font-size:0.75rem; min-height:36px; padding:4px 8px; width:100%;" onclick="generateBeatAudio(${item.scene})">🎙️ Voiceover Line</button>
                                            <button id="btnBeatClip_${item.scene}" class="btn-apple" style="font-size:0.75rem; min-height:36px; padding:4px 8px; width:100%; background:linear-gradient(135deg, #FF9500, #FF2D55);" onclick="generateBeatClip(${item.scene})">🎬 Generate Mini-Clip</button>
                                        </div>

                                        <!-- Dedicated Per-Card Visual Progress Bar -->
                                        <div id="cardProgress_${item.scene}" style="display:none; margin-top:6px; padding:8px 12px; background:var(--bg-card-secondary); border:1px solid var(--accent-apple); border-radius:10px;">
                                            <div style="display:flex; justify-content:space-between; font-size:0.75rem; font-weight:700; color:var(--accent-apple); margin-bottom:4px;">
                                                <span id="cardStatus_${item.scene}">⏳ Processing Beat #${item.scene}...</span>
                                                <span style="font-size:0.7rem; color:var(--accent-apple);">Synthesizing...</span>
                                            </div>
                                            <div class="progress-bar" style="height:6px; margin:0;"><div id="cardFill_${item.scene}" class="progress-fill" style="width:100%;"></div></div>
                                        </div>

                                        <!-- Inline Voiceover Audio Player -->
                                        <div id="beatAudioBox_${item.scene}" style="display:none; margin-top:4px;">
                                            <div style="font-size:0.72rem; font-weight:700; color:var(--accent-apple); margin-bottom:2px;">🎙️ Line Voiceover MP3:</div>
                                            <audio id="beatAudioPlayer_${item.scene}" controls style="width:100%; height:32px; display:block;"></audio>
                                        </div>

                                        <!-- Inline Mini-Clip Video Player -->
                                        <div id="beatPlayer_${item.scene}" style="display:none; margin-top:4px;">
                                            <div style="font-size:0.72rem; font-weight:700; color:#34c759; margin-bottom:4px;">✓ 16:9 Mini-Clip #${item.scene} Video Player:</div>
                                            <video id="beatVideo_${item.scene}" controls style="width:100%; aspect-ratio:16/9; border-radius:8px; background:#000; display:block;" src=""></video>
                                        </div>
                                    </div>
                                `;
                                container.appendChild(card);
                            });

                            breakdownCard.classList.add('active');
                        } else if (data.mode === 'video' && data.result) {
                            const videoElement = document.getElementById('videoElement');
                            const downloadVideoLink = document.getElementById('downloadVideoLink');
                            const videoCard = document.getElementById('videoCard');
                            const qaReportBadge = document.getElementById('qaReportBadge');

                            videoElement.src = data.result.videoUrl;
                            downloadVideoLink.href = data.result.videoUrl;
                            downloadVideoLink.download = data.result.videoFilename;

                            if (data.result.qaReport && qaReportBadge) {
                                qaReportBadge.textContent = data.result.qaReport;
                                qaReportBadge.style.display = 'block';
                            }

                            if (data.result.miniClips && data.result.miniClips.length > 0) {
                                renderMiniClipsGrid(data.result.miniClips);
                            }

                            videoCard.classList.add('active');
                            videoElement.play();
                            videoCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        }
                    } else if (data.status === 'failed') {
                        clearInterval(pollInterval);
                        localStorage.removeItem('active_job_id');
                        progressBox.classList.remove('active');
                        if (videoProgressBox) videoProgressBox.classList.remove('active');
                        const renderBtn = document.getElementById('renderVideoBtn');
                        if (renderBtn) {
                            renderBtn.disabled = false;
                            renderBtn.innerHTML = '⚡ Render 1080p MP4 Video';
                        }
                        alert(data.status_text || 'Job failed');
                    }
                } catch (e) {
                    console.log('Polling status error:', e);
                }
            }, 1500);
        }

        let perBeatImages = {};
        let activeMiniClips = [];
        let isBatchPaused = false;
        let currentBatchTask = null; // 'voiceovers' or 'miniclips'
        let currentBatchIndex = 0;

        function updateChecklistStatus() {
            const chk1 = document.getElementById('chkStep1');
            const chk2 = document.getElementById('chkStep2');
            const chk3 = document.getElementById('chkStep3');
            const counter = document.getElementById('checklistCounter');

            const totalBeats = (lastBreakdownData && lastBreakdownData.length) ? lastBreakdownData.length : 0;
            const uploadedCount = Object.keys(perBeatImages).length;
            
            if (chk1) {
                if (totalBeats > 0 && uploadedCount >= totalBeats) {
                    chk1.checked = true;
                } else if (uploadedCount > 0) {
                    chk1.checked = true;
                }
            }

            if (chk2 && totalBeats > 0) {
                let countAudio = 0;
                for (let i = 0; i < totalBeats; i++) {
                    const beatNum = lastBreakdownData[i].scene;
                    const audioEl = document.getElementById(`beatAudioPlayer_${beatNum}`);
                    if (audioEl && audioEl.src && !audioEl.src.endsWith('#') && audioEl.src !== window.location.href) {
                        countAudio++;
                    }
                }
                if (countAudio >= totalBeats) chk2.checked = true;
            }

            if (chk3 && totalBeats > 0 && activeMiniClips.length >= totalBeats) {
                chk3.checked = true;
            }

            let completedCount = 0;
            if (chk1 && chk1.checked) completedCount++;
            if (chk2 && chk2.checked) completedCount++;
            if (chk3 && chk3.checked) completedCount++;

            if (counter) counter.textContent = `${completedCount} / 3 Completed`;
        }

        function toggleBatchPause() {
            const btn = document.getElementById('btnPauseResume');
            const statusDetail = document.getElementById('autoStatusTextDetail');

            if (!isBatchPaused) {
                isBatchPaused = true;
                if (btn) btn.textContent = '▶️ Resume';
                if (statusDetail) statusDetail.textContent = `⏸️ Paused at Beat #${currentBatchIndex + 1}. Click Resume to continue.`;
            } else {
                isBatchPaused = false;
                if (btn) btn.textContent = '⏸️ Pause';
                if (currentBatchTask === 'voiceovers') {
                    autoGenerateAllBeatVoiceovers(true);
                } else if (currentBatchTask === 'miniclips') {
                    autoRenderAllSceneMiniClips(true);
                }
            }
        }

        function handlePerBeatImageUpload(beatNum, inputEl) {
            if (inputEl.files && inputEl.files[0]) {
                const file = inputEl.files[0];
                perBeatImages[beatNum] = file;
                
                const reader = new FileReader();
                reader.onload = function(e) {
                    const previewBox = document.getElementById('beatPreview_' + beatNum);
                    const previewImg = document.getElementById('beatImg_' + beatNum);
                    if (previewBox && previewImg) {
                        previewImg.src = e.target.result;
                        previewBox.style.display = 'block';
                    }
                };
                reader.readAsDataURL(file);
                updateChecklistStatus();
            }
        }

        async function handleBatchZipOrImagesUpload(inputEl) {
            const files = inputEl.files;
            const statusEl = document.getElementById('batchUploadStatus');
            if (!files || files.length === 0) return;

            if (statusEl) {
                statusEl.style.display = 'block';
                statusEl.textContent = '⏳ Processing and extracting batch images...';
            }

            let fileList = Array.from(files);

            // If single ZIP file uploaded, extract with JSZip
            if (fileList.length === 1 && fileList[0].name.toLowerCase().endsWith('.zip')) {
                try {
                    const zipFile = fileList[0];
                    const zip = await JSZip.loadAsync(zipFile);
                    fileList = [];
                    const zipEntries = Object.keys(zip.files).filter(filename => {
                        const lower = filename.toLowerCase();
                        return !zip.files[filename].dir && (lower.endsWith('.jpg') || lower.endsWith('.jpeg') || lower.endsWith('.png') || lower.endsWith('.webp'));
                    });

                    for (const filename of zipEntries) {
                        const fileData = await zip.files[filename].async('blob');
                        const cleanName = filename.split('/').pop();
                        const imageFile = new File([fileData], cleanName, { type: fileData.type || 'image/jpeg' });
                        fileList.push(imageFile);
                    }
                } catch (err) {
                    alert('Error extracting ZIP archive: ' + err.message);
                    if (statusEl) statusEl.style.display = 'none';
                    return;
                }
            }

            // Sort files numerically by extracting digits (1.jpg -> 1, 2.jpg -> 2, 10.jpg -> 10...)
            fileList.sort((a, b) => {
                const numA = parseInt((a.name.match(/\d+/) || [99999])[0], 10);
                const numB = parseInt((b.name.match(/\d+/) || [99999])[0], 10);
                return numA - numB;
            });

            let matchedCount = 0;
            fileList.forEach((file, index) => {
                const match = file.name.match(/\d+/);
                let beatNum = match ? parseInt(match[0], 10) : (index + 1);

                if (beatNum <= 0) beatNum = index + 1;

                perBeatImages[beatNum] = file;
                matchedCount++;

                const reader = new FileReader();
                reader.onload = function(e) {
                    const previewBox = document.getElementById('beatPreview_' + beatNum);
                    const previewImg = document.getElementById('beatImg_' + beatNum);
                    if (previewBox && previewImg) {
                        previewImg.src = e.target.result;
                        previewBox.style.display = 'block';
                    }
                };
                reader.readAsDataURL(file);
            });

            if (statusEl) {
                statusEl.style.display = 'block';
                statusEl.textContent = `✓ Successfully assigned ${matchedCount} images sequentially to Beat Cards! (1.jpg -> Beat #1, 2.jpg -> Beat #2...)`;
            }

            const chk1 = document.getElementById('chkStep1');
            if (chk1) chk1.checked = true;
            updateChecklistStatus();
        }

        async function generateBeatAudio(beatNum) {
            const btn = document.getElementById(`btnBeatAudio_${beatNum}`);
            const progressBox = document.getElementById(`cardProgress_${beatNum}`);
            const statusText = document.getElementById(`cardStatus_${beatNum}`);

            const activeJobId = localStorage.getItem('last_active_job_id') || '';
            if (!activeJobId) {
                alert('Please click Scene Cuts first to initialize your job!');
                return;
            }
            if (btn) {
                btn.disabled = true;
                btn.textContent = '⏳ Synthesizing...';
            }
            if (progressBox && statusText) {
                statusText.textContent = `🎙️ Synthesizing Voiceover #${beatNum}...`;
                progressBox.style.display = 'block';
            }

            try {
                const chosenVoice = (typeof selectedVoice !== 'undefined' && selectedVoice) ? selectedVoice : 'andrew';
                const sliderVal = document.getElementById('rateSlider') ? parseInt(document.getElementById('rateSlider').value || 1) : 1;
                const rateVal = `${sliderVal >= 0 ? '+' : ''}${sliderVal}%`;

                const res = await fetch('/api/generate-beat-audio', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        job_id: activeJobId,
                        scene_index: beatNum,
                        voice: chosenVoice,
                        rate: rateVal
                    })
                });

                if (!res.ok) {
                    const rawText = await res.text();
                    let errMsg = rawText;
                    try {
                        const parsed = JSON.parse(rawText);
                        if (parsed.error) errMsg = parsed.error;
                    } catch (e) {}
                    alert('Server Error (' + res.status + '): ' + errMsg);
                    return;
                }

                const data = await res.json();
                if (data.status === 'success') {
                    const audioBox = document.getElementById(`beatAudioBox_${beatNum}`);
                    const audioPlayer = document.getElementById(`beatAudioPlayer_${beatNum}`);
                    if (audioBox && audioPlayer) {
                        audioPlayer.src = data.audioUrl;
                        audioBox.style.display = 'block';
                        audioPlayer.play();
                    }
                    updateChecklistStatus();
                } else {
                    alert(data.error || 'Failed to generate beat audio.');
                }
            } catch (e) {
                alert('Error: ' + e.message);
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.textContent = '🎙️ Voiceover Line';
                }
                if (progressBox) {
                    progressBox.style.display = 'none';
                }
            }
        }

        async function generateBeatClip(beatNum) {
            const btn = document.getElementById(`btnBeatClip_${beatNum}`);
            const progressBox = document.getElementById(`cardProgress_${beatNum}`);
            const statusText = document.getElementById(`cardStatus_${beatNum}`);

            const activeJobId = localStorage.getItem('last_active_job_id') || '';
            
            if (!perBeatImages[beatNum]) {
                alert(`Please upload an image for Beat #${beatNum} before generating its mini-clip!`);
                return;
            }
            if (!activeJobId) {
                alert('Please click Scene Cuts first to initialize your job!');
                return;
            }

            if (btn) {
                btn.disabled = true;
                btn.textContent = '⏳ Rendering Clip...';
            }
            if (progressBox && statusText) {
                statusText.textContent = `🎬 Rendering 16:9 Mini-Clip #${beatNum}...`;
                progressBox.style.display = 'block';
            }

            try {
                const formData = new FormData();
                formData.append('job_id', activeJobId);
                formData.append('scene_index', beatNum);
                formData.append('image', perBeatImages[beatNum]);

                const res = await fetch('/api/generate-beat-clip', {
                    method: 'POST',
                    body: formData
                });

                if (!res.ok) {
                    const rawText = await res.text();
                    let errMsg = rawText;
                    try {
                        const parsed = JSON.parse(rawText);
                        if (parsed.error) errMsg = parsed.error;
                    } catch (e) {}
                    alert('Server Error (' + res.status + '): ' + errMsg);
                    return;
                }

                const data = await res.json();
                if (data.status === 'success') {
                    const playerBox = document.getElementById(`beatPlayer_${beatNum}`);
                    const videoEl = document.getElementById(`beatVideo_${beatNum}`);
                    if (playerBox && videoEl) {
                        videoEl.src = data.clipUrl;
                        playerBox.style.display = 'block';
                        videoEl.play();
                    }

                    // Update active mini-clips list for timeline studio
                    const existingIdx = activeMiniClips.findIndex(c => c.sceneIndex === beatNum);
                    const clipObj = {
                        sceneIndex: beatNum,
                        filename: data.filename,
                        url: data.clipUrl,
                        durSec: data.durSec,
                        text: `Beat #${beatNum}`
                    };
                    if (existingIdx >= 0) {
                        activeMiniClips[existingIdx] = clipObj;
                    } else {
                        activeMiniClips.push(clipObj);
                        activeMiniClips.sort((a, b) => a.sceneIndex - b.sceneIndex);
                    }
                    renderMiniClipsGrid(activeMiniClips);
                    updateChecklistStatus();
                } else {
                    alert(data.error || 'Failed to render mini-clip.');
                }
            } catch (e) {
                alert('Error rendering mini-clip: ' + e.message);
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.textContent = '🎬 Generate Mini-Clip';
                }
                if (progressBox) {
                    progressBox.style.display = 'none';
                }
            }
        }

        async function autoGenerateAllBeatVoiceovers(isResuming = false) {
            if (!lastBreakdownData || !lastBreakdownData.length) {
                alert('Please click Scene Cuts first to generate your beat cards!');
                return;
            }

            const masterBtn = document.getElementById('btnAutoAllVoiceovers');
            const autoStatus = document.getElementById('autoStatusText');
            const autoBarBox = document.getElementById('autoProgressContainer');
            const autoFill = document.getElementById('autoProgressBarFill');
            const statusDetail = document.getElementById('autoStatusTextDetail');
            const pauseBtn = document.getElementById('btnPauseResume');

            currentBatchTask = 'voiceovers';

            if (!isResuming) {
                isBatchPaused = false;
                currentBatchIndex = 0;
                if (pauseBtn) pauseBtn.textContent = '⏸️ Pause';
            }

            if (masterBtn) { masterBtn.disabled = true; }
            if (autoStatus) { autoStatus.style.display = 'inline'; autoStatus.textContent = '⏳ Synthesizing Voiceovers...'; }
            if (autoBarBox) { autoBarBox.style.display = 'block'; }

            const total = lastBreakdownData.length;
            for (let i = currentBatchIndex; i < total; i++) {
                if (isBatchPaused) {
                    currentBatchIndex = i;
                    if (masterBtn) { masterBtn.disabled = false; }
                    return;
                }

                currentBatchIndex = i;
                const beatNum = lastBreakdownData[i].scene;
                const pct = Math.round(((i + 1) / total) * 100);
                if (autoFill) autoFill.style.width = `${pct}%`;
                
                const statusMsg = `🎙️ Synthesizing Voiceover ${i + 1}/${total} (Beat #${beatNum})...`;
                if (autoStatus) autoStatus.textContent = statusMsg;
                if (statusDetail) statusDetail.textContent = statusMsg;

                // Check if beat audio is already generated
                const existingAudio = document.getElementById(`beatAudioPlayer_${beatNum}`);
                if (existingAudio && existingAudio.src && !existingAudio.src.endsWith('#') && existingAudio.src !== window.location.href) {
                    console.log(`Skipping already generated voiceover for Beat #${beatNum}`);
                } else {
                    await generateBeatAudio(beatNum);
                    // Short rate-limit protection pause
                    await new Promise(r => setTimeout(r, 250));
                }
            }

            const chk2 = document.getElementById('chkStep2');
            if (chk2) chk2.checked = true;
            updateChecklistStatus();

            const finishMsg = `✓ All ${total} Beat Voiceovers Synthesized & Trimmed Clean!`;
            if (autoStatus) autoStatus.textContent = finishMsg;
            if (statusDetail) statusDetail.textContent = finishMsg;
            if (masterBtn) { masterBtn.disabled = false; }
        }

        async function autoRenderAllSceneMiniClips(isResuming = false) {
            if (!lastBreakdownData || !lastBreakdownData.length) {
                alert('Please click Scene Cuts first to generate your beat cards!');
                return;
            }

            const uploadedBeats = Object.keys(perBeatImages);
            if (!uploadedBeats.length) {
                alert('Please upload an image for at least one Beat Card before running 1-Click Auto-Render!');
                return;
            }

            const masterBtn = document.getElementById('btnAutoAllMiniClips');
            const autoStatus = document.getElementById('autoStatusText');
            const autoBarBox = document.getElementById('autoProgressContainer');
            const autoFill = document.getElementById('autoProgressBarFill');
            const statusDetail = document.getElementById('autoStatusTextDetail');
            const pauseBtn = document.getElementById('btnPauseResume');

            currentBatchTask = 'miniclips';

            if (!isResuming) {
                isBatchPaused = false;
                currentBatchIndex = 0;
                if (pauseBtn) pauseBtn.textContent = '⏸️ Pause';
            }

            if (masterBtn) { masterBtn.disabled = true; }
            if (autoStatus) { autoStatus.style.display = 'inline'; autoStatus.textContent = '⏳ Auto-Rendering Mini-Clips...'; }
            if (autoBarBox) { autoBarBox.style.display = 'block'; }

            const total = lastBreakdownData.length;
            for (let i = currentBatchIndex; i < total; i++) {
                if (isBatchPaused) {
                    currentBatchIndex = i;
                    if (masterBtn) { masterBtn.disabled = false; }
                    return;
                }

                currentBatchIndex = i;
                const beatNum = lastBreakdownData[i].scene;
                if (perBeatImages[beatNum]) {
                    const pct = Math.round(((i + 1) / total) * 100);
                    if (autoFill) autoFill.style.width = `${pct}%`;
                    
                    const statusMsg = `🎬 Auto-Rendering Mini-Clip ${i + 1}/${total} (Beat #${beatNum})...`;
                    if (autoStatus) autoStatus.textContent = statusMsg;
                    if (statusDetail) statusDetail.textContent = statusMsg;

                    // Check if mini-clip is already rendered
                    const existingVideo = document.getElementById(`beatVideo_${beatNum}`);
                    if (existingVideo && existingVideo.src && !existingVideo.src.endsWith('#') && existingVideo.src !== window.location.href) {
                        console.log(`Skipping already rendered mini-clip for Beat #${beatNum}`);
                    } else {
                        await generateBeatClip(beatNum);
                        // Short rate-limit protection pause
                        await new Promise(r => setTimeout(r, 250));
                    }
                }
            }

            const chk3 = document.getElementById('chkStep3');
            if (chk3) chk3.checked = true;
            updateChecklistStatus();

            const finishMsg = `✓ All Scene Mini-Clips Auto-Rendered & Loaded into Timeline Studio!`;
            if (autoStatus) autoStatus.textContent = finishMsg;
            if (statusDetail) statusDetail.textContent = finishMsg;
            if (masterBtn) { masterBtn.disabled = false; }
        }

        function renderMiniClipsGrid(clips) {
            activeMiniClips = clips;
            const gridContainer = document.getElementById('miniClipsGrid');
            const studioCard = document.getElementById('miniClipsStudioCard');
            if (!gridContainer || !studioCard) return;

            gridContainer.innerHTML = '';
            clips.forEach(c => {
                const card = document.createElement('div');
                card.style.cssText = 'background:var(--bg-card-secondary); border:1px solid var(--border-subtle); border-radius:14px; padding:12px; display:flex; flex-direction:column; gap:8px; box-shadow:var(--shadow-card);';
                card.innerHTML = `
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-weight:800; font-size:0.85rem; color:var(--accent-apple);"># Beat ${c.sceneIndex}</span>
                        <span style="font-size:0.72rem; font-weight:700; background:rgba(0,113,227,0.12); color:var(--accent-apple); padding:2px 8px; border-radius:10px;">${c.durSec}s</span>
                    </div>
                    <video controls style="width:100%; aspect-ratio:16/9; border-radius:8px; background:#000;" src="${c.url}"></video>
                    <div style="font-size:0.75rem; color:var(--text-secondary); line-height:1.3; height:32px; overflow:hidden;">"${c.text}"</div>
                    <label style="display:flex; align-items:center; gap:8px; margin-top:4px; font-size:0.8rem; font-weight:700; color:var(--text-primary); cursor:pointer;">
                        <input type="checkbox" class="clip-select-checkbox" data-filename="${c.filename}" data-idx="${c.sceneIndex}" data-dur="${c.durSec}" checked onchange="updateTimelineSequence()" />
                        Include in Video Timeline
                    </label>
                `;
                gridContainer.appendChild(card);
            });

            studioCard.style.display = 'block';
            updateTimelineSequence();
        }

        function toggleSelectAllClips(status) {
            const checkboxes = document.querySelectorAll('.clip-select-checkbox');
            checkboxes.forEach(cb => cb.checked = status);
            updateTimelineSequence();
        }

        function updateTimelineSequence() {
            const strip = document.getElementById('timelineSequenceStrip');
            const counter = document.getElementById('selectedClipsCounter');
            if (!strip) return;

            const checkboxes = document.querySelectorAll('.clip-select-checkbox:checked');
            strip.innerHTML = '';

            let totalDur = 0;
            checkboxes.forEach((cb, i) => {
                const idx = cb.getAttribute('data-idx');
                const dur = parseFloat(cb.getAttribute('data-dur')) || 0;
                totalDur += dur;

                const badge = document.createElement('div');
                badge.style.cssText = 'flex:0 0 auto; background:var(--bg-input); border:1px solid var(--accent-apple); padding:8px 12px; border-radius:10px; font-size:0.78rem; font-weight:700; color:var(--text-primary); display:flex; align-items:center; gap:6px;';
                badge.innerHTML = `<span>🎬 #${idx}</span> <span style="color:var(--text-secondary); font-size:0.7rem;">(${dur}s)</span>`;
                strip.appendChild(badge);
            });

            if (counter) {
                counter.textContent = `${checkboxes.length} Clips Selected (${totalDur.toFixed(1)}s Total)`;
            }
        }

        async function exportTimelineMasterVideo() {
            const checkboxes = document.querySelectorAll('.clip-select-checkbox:checked');
            if (!checkboxes || !checkboxes.length) {
                alert('Please select at least one mini-clip to export your timeline!');
                return;
            }

            const selectedFilenames = Array.from(checkboxes).map(cb => cb.getAttribute('data-filename'));
            const exportBtn = document.getElementById('exportTimelineBtn');
            if (exportBtn) {
                exportBtn.disabled = true;
                exportBtn.innerHTML = '⏳ Exporting Master Video Timeline...';
            }

            try {
                const res = await fetch('/api/export-timeline', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ clip_filenames: selectedFilenames })
                });

                const data = await res.json();
                if (data.status === 'success') {
                    const videoElement = document.getElementById('videoElement');
                    const downloadVideoLink = document.getElementById('downloadVideoLink');
                    const videoCard = document.getElementById('videoCard');
                    const qaReportBadge = document.getElementById('qaReportBadge');

                    videoElement.src = data.videoUrl;
                    downloadVideoLink.href = data.videoUrl;
                    downloadVideoLink.download = data.videoFilename;

                    if (qaReportBadge) {
                        qaReportBadge.textContent = data.qaReport;
                        qaReportBadge.style.display = 'block';
                    }

                    videoCard.classList.add('active');
                    videoElement.play();
                    videoCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
                } else {
                    alert(data.error || 'Failed to export timeline video.');
                }
            } catch (e) {
                alert('Error exporting timeline: ' + e.message);
            } finally {
                if (exportBtn) {
                    exportBtn.disabled = false;
                    exportBtn.innerHTML = '🚀 Export Final Master Video (.MP4)';
                }
            }
        }

        function uploadAndRenderVideo() {
            const fileInput = document.getElementById('videoImagesInput');
            const zipOrBatchFiles = fileInput ? fileInput.files : null;
            
            const hasPerBeatImgs = Object.keys(perBeatImages).length > 0;
            const hasZipOrBatch = zipOrBatchFiles && zipOrBatchFiles.length > 0;

            if (!hasPerBeatImgs && !hasZipOrBatch) {
                alert('Please upload an image for each Beat Card before rendering your video!');
                return;
            }

            const formData = new FormData();
            const activeJobId = localStorage.getItem('last_active_job_id') || '';
            formData.append('job_id', activeJobId);

            if (hasPerBeatImgs) {
                for (const beatNum in perBeatImages) {
                    formData.append(`beat_image_${beatNum}`, perBeatImages[beatNum]);
                }
            }

            if (hasZipOrBatch) {
                if (zipOrBatchFiles.length === 1 && zipOrBatchFiles[0].name.toLowerCase().endsWith('.zip')) {
                    formData.append('zip_file', zipOrBatchFiles[0]);
                } else {
                    for (let i = 0; i < zipOrBatchFiles.length; i++) {
                        formData.append('images', zipOrBatchFiles[i]);
                    }
                }
            }

            document.getElementById('videoCard').classList.remove('active');
            
            const progressBox = document.getElementById('progressBox');
            const progressPercent = document.getElementById('progressPercent');
            const progressBarFill = document.getElementById('progressBarFill');
            const progressStatus = document.getElementById('progressStatus');

            const videoProgressBox = document.getElementById('videoProgressBox');
            const videoProgressPercent = document.getElementById('videoProgressPercent');
            const videoProgressBarFill = document.getElementById('videoProgressBarFill');
            const videoProgressStatus = document.getElementById('videoProgressStatus');

            const renderBtn = document.getElementById('renderVideoBtn');
            if (renderBtn) {
                renderBtn.disabled = true;
                renderBtn.innerHTML = '⏳ Uploading & Rendering 1080p Video...';
            }

            progressBox.classList.add('active');
            if (videoProgressBox) {
                videoProgressBox.classList.add('active');
                videoProgressBox.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }

            const initPct = '0%';
            progressPercent.textContent = initPct;
            if (videoProgressPercent) videoProgressPercent.textContent = initPct;

            progressBarFill.style.width = initPct;
            if (videoProgressBarFill) videoProgressBarFill.style.width = initPct;

            const initStatus = '📦 Uploading ZIP file to server...';
            progressStatus.textContent = initStatus;
            if (videoProgressStatus) videoProgressStatus.textContent = initStatus;

            const xhr = new XMLHttpRequest();
            xhr.open('POST', '/api/assemble-video', true);

            xhr.upload.onprogress = function(e) {
                if (e.lengthComputable) {
                    const uploadPct = Math.round((e.loaded / e.total) * 100);
                    const mbLoaded = (e.loaded / (1024 * 1024)).toFixed(1);
                    const mbTotal = (e.total / (1024 * 1024)).toFixed(1);
                    
                    const pctStr = `${uploadPct}%`;
                    const statusStr = `📦 Uploading ZIP file: ${uploadPct}% (${mbLoaded} MB / ${mbTotal} MB)...`;

                    progressBarFill.style.width = pctStr;
                    if (videoProgressBarFill) videoProgressBarFill.style.width = pctStr;

                    progressPercent.textContent = pctStr;
                    if (videoProgressPercent) videoProgressPercent.textContent = pctStr;

                    progressStatus.textContent = statusStr;
                    if (videoProgressStatus) videoProgressStatus.textContent = statusStr;
                }
            };

            xhr.onload = function() {
                if (xhr.status === 200) {
                    try {
                        const data = JSON.parse(xhr.responseText);
                        if (data.job_id) {
                            startPollingJob(data.job_id);
                        }
                    } catch (e) {
                        alert('Error parsing server response.');
                        progressBox.classList.remove('active');
                        if (videoProgressBox) videoProgressBox.classList.remove('active');
                        if (renderBtn) { renderBtn.disabled = false; renderBtn.innerHTML = '⚡ Render 1080p MP4 Video'; }
                    }
                } else {
                    try {
                        const errData = JSON.parse(xhr.responseText);
                        alert(errData.error || 'Video assembly upload failed.');
                    } catch (e) {
                        alert('Upload error (status ' + xhr.status + ').');
                    }
                    progressBox.classList.remove('active');
                    if (videoProgressBox) videoProgressBox.classList.remove('active');
                    if (renderBtn) { renderBtn.disabled = false; renderBtn.innerHTML = '⚡ Render 1080p MP4 Video'; }
                }
            };

            xhr.onerror = function() {
                alert('Network error while uploading video assets.');
                progressBox.classList.remove('active');
                if (videoProgressBox) videoProgressBox.classList.remove('active');
                if (renderBtn) { renderBtn.disabled = false; renderBtn.innerHTML = '⚡ Render 1080p MP4 Video'; }
            };

            xhr.send(formData);
        }

        async function generateStream(mode) {
            updateWordCount();
            const scriptEl = document.getElementById('scriptText');
            const text = scriptEl ? scriptEl.value.trim() : '';
            if (!text) {
                alert('Please paste a script first!');
                return;
            }

            const filenameInput = document.getElementById('filenameInput');
            const customFilename = filenameInput ? filenameInput.value.trim() : '';

            const audioCard = document.getElementById('audioCard');
            const srtCard = document.getElementById('srtCard');
            const breakdownCard = document.getElementById('breakdownCard');
            if (audioCard) audioCard.classList.remove('active');
            if (srtCard) srtCard.classList.remove('active');
            if (breakdownCard) breakdownCard.classList.remove('active');

            const progressBox = document.getElementById('progressBox');
            const progressTitle = document.getElementById('progressTitle');
            const progressStatus = document.getElementById('progressStatus');
            const progressBarFill = document.getElementById('progressBarFill');
            const progressPercent = document.getElementById('progressPercent');

            if (progressBox) progressBox.classList.add('active');
            if (progressTitle) progressTitle.textContent = mode === 'breakdown' ? '🎬 Generating Scene Cuts...' : '🎵 Synthesizing Voiceover...';
            if (progressStatus) progressStatus.textContent = '🚀 Sending script to cloud server...';
            if (progressBarFill) progressBarFill.style.width = '10%';
            if (progressPercent) progressPercent.textContent = '10%';

            try {
                const response = await fetch('/api/start-job', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        text: text,
                        voice: typeof selectedVoice !== 'undefined' ? selectedVoice : 'andrew',
                        rate: typeof currentRateStr !== 'undefined' ? currentRateStr : '+1%',
                        filename: customFilename || `youtube_voiceover_${Date.now()}.mp3`,
                        mode: mode
                    })
                });

                const data = await response.json();
                if (data.error) {
                    alert('Error: ' + data.error);
                    if (progressBox) progressBox.classList.remove('active');
                    return;
                }

                if (data.job_id) {
                    localStorage.setItem('active_job_id', data.job_id);
                    startPollingJob(data.job_id);
                }
            } catch (err) {
                alert('Connection error: ' + err.message);
                if (progressBox) progressBox.classList.remove('active');
            }
        }

        window.addEventListener('load', () => {
            const savedJobId = localStorage.getItem('active_job_id');
            if (savedJobId) {
                startPollingJob(savedJobId);
            }
        });
    