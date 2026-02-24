import { useState, useEffect, useRef, useCallback } from 'react';
import { useApp } from '@modelcontextprotocol/ext-apps/react';
import * as THREE from 'three';
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader.js';

interface ItemData {
    id: string;
    sku: string;
    name: string;
    type: string;
    unit_price: number;
    uom?: string;
    reorder_qty?: number;
    image_url?: string;
    model_obj?: string;  // 3D model data from tool
}

export default function ItemInspectViewer() {
    const [status, setStatus] = useState<'connecting' | 'ready' | 'loading'>('connecting');
    const [itemData, setItemData] = useState<ItemData | null>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const sceneRef = useRef<{
        scene: THREE.Scene;
        camera: THREE.PerspectiveCamera;
        renderer: THREE.WebGLRenderer;
        mesh: THREE.Mesh | null;
        rotationY: number;
        rotationX: number;
        zoom: number;
        isDragging: boolean;
        lastMouseX: number;
        lastMouseY: number;
    } | null>(null);
    const animationFrameRef = useRef<number | null>(null);

    const { app, isConnected, error } = useApp({
        appInfo: { name: 'ItemInspectViewer', version: '1.0.0' },
        capabilities: {},
        onAppCreated: (appInstance) => {
            console.log('Item Inspector App created');

            // Listen for tool input (the arguments passed to catalog_inspect_item)
            appInstance.ontoolinput = (params: any) => {
                console.log('Received tool input:', params);
                if (params.arguments && params.arguments.sku) {
                    setStatus('loading');
                    // The tool will be called and we'll get the result
                }
            };

            // Listen for tool result with item data
            appInstance.ontoolresult = (params: any) => {
                console.log('Received tool result:', params);

                // Handle error responses
                if (params.isError) {
                    console.error('Tool returned error:', params);
                    setStatus('ready');
                    return;
                }

                if (params.content) {
                    try {
                        for (const item of params.content) {
                            if (item.type === 'text') {
                                const parsed = JSON.parse(item.text);
                                if (parsed.data) {
                                    setItemData(parsed.data as ItemData);
                                    setStatus('ready');
                                    return;
                                }
                            }
                        }
                    } catch (e) {
                        console.error('Failed to parse tool result:', e);
                    }
                }

                // Fallback: set ready even if parsing failed
                setStatus('ready');
            };
        },
    });

    // Once connected, mark as ready immediately
    useEffect(() => {
        if (isConnected && status === 'connecting') {
            setStatus('ready');
        }
    }, [isConnected, status]);

    // Initialize Three.js scene (once)
    useEffect(() => {
        console.log('=== Three.js scene initialization useEffect triggered ===');
        console.log('status:', status);
        console.log('isConnected:', isConnected);
        console.log('containerRef.current:', containerRef.current);
        console.log('sceneRef.current:', sceneRef.current);

        // Only initialize once we're connected and ready, and the ref is available
        if (!isConnected || status !== 'ready' || !containerRef.current || sceneRef.current) {
            console.log('Early return - isConnected:', isConnected, 'status:', status, 'containerRef:', !!containerRef.current, 'sceneRef:', !!sceneRef.current);
            return;
        }

        console.log('Initializing Three.js scene...');
        const container = containerRef.current;
        const width = container.clientWidth;
        const height = container.clientHeight;
        console.log(`Container size: ${width}x${height}`);

        // Scene setup
        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0x0a0a0a);

        // Camera setup
        const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
        camera.position.set(0, 0, 5); // Move camera back
        camera.lookAt(0, 0, 0); // Look at center
        console.log('Camera position:', camera.position);
        console.log('Camera looking at:', new THREE.Vector3(0, 0, 0));

        // Renderer setup
        const renderer = new THREE.WebGLRenderer({ antialias: true });
        renderer.setSize(width, height);
        renderer.domElement.style.display = 'block';
        renderer.domElement.style.width = '100%';
        renderer.domElement.style.height = '100%';
        container.appendChild(renderer.domElement);
        console.log('Renderer appended to container');
        console.log('Renderer canvas:', renderer.domElement);

        // Lighting
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
        scene.add(ambientLight);
        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
        directionalLight.position.set(5, 5, 5);
        scene.add(directionalLight);

        sceneRef.current = {
            scene,
            camera,
            renderer,
            mesh: null,
            rotationY: Math.PI / 2, // Start rotated 90 degrees (π/2 radians)
            rotationX: 0,
            zoom: 1.0,
            isDragging: false,
            lastMouseX: 0,
            lastMouseY: 0,
        };

        // Animation loop
        let frameCount = 0;
        const animate = () => {
            animationFrameRef.current = requestAnimationFrame(animate);

            if (sceneRef.current && sceneRef.current.mesh) {
                sceneRef.current.mesh.rotation.y = sceneRef.current.rotationY;
                sceneRef.current.mesh.rotation.x = sceneRef.current.rotationX;
            }

            // Apply zoom by adjusting camera distance
            if (sceneRef.current) {
                camera.position.z = 5 / sceneRef.current.zoom;
            }

            renderer.render(scene, camera);

            // Log first few frames for debugging
            if (frameCount < 3) {
                console.log(`Frame ${frameCount} rendered`);
                frameCount++;
            }
        };
        console.log('Starting animation loop');
        animate();

        // Handle window resize
        const handleResize = () => {
            if (!containerRef.current || !sceneRef.current) return;
            const newWidth = containerRef.current.clientWidth;
            const newHeight = containerRef.current.clientHeight;
            sceneRef.current.camera.aspect = newWidth / newHeight;
            sceneRef.current.camera.updateProjectionMatrix();
            sceneRef.current.renderer.setSize(newWidth, newHeight);
        };
        window.addEventListener('resize', handleResize);

        // Mouse event handlers
        const handleMouseDown = (e: MouseEvent) => {
            if (sceneRef.current) {
                sceneRef.current.isDragging = true;
                sceneRef.current.lastMouseX = e.clientX;
                sceneRef.current.lastMouseY = e.clientY;
            }
        };

        const handleMouseMove = (e: MouseEvent) => {
            if (sceneRef.current && sceneRef.current.isDragging) {
                const deltaX = e.clientX - sceneRef.current.lastMouseX;
                const deltaY = e.clientY - sceneRef.current.lastMouseY;

                // Y-axis rotation (horizontal drag)
                sceneRef.current.rotationY += deltaX * 0.01;

                // X-axis rotation (vertical drag), limited to ±45 degrees
                const maxRotationX = Math.PI / 4; // 45 degrees in radians
                sceneRef.current.rotationX += deltaY * 0.01;
                sceneRef.current.rotationX = Math.max(-maxRotationX, Math.min(maxRotationX, sceneRef.current.rotationX));

                sceneRef.current.lastMouseX = e.clientX;
                sceneRef.current.lastMouseY = e.clientY;
            }
        };

        const handleMouseUp = () => {
            if (sceneRef.current) {
                sceneRef.current.isDragging = false;
            }
        };

        const handleWheel = (e: WheelEvent) => {
            e.preventDefault();
            if (sceneRef.current) {
                // Zoom with scroll wheel, limited to 50%-300%
                const zoomSpeed = 0.001;
                sceneRef.current.zoom -= e.deltaY * zoomSpeed;
                sceneRef.current.zoom = Math.max(0.5, Math.min(3.0, sceneRef.current.zoom));
            }
        };

        container.addEventListener('mousedown', handleMouseDown);
        container.addEventListener('wheel', handleWheel, { passive: false });
        window.addEventListener('mousemove', handleMouseMove);
        window.addEventListener('mouseup', handleMouseUp);

        // Cleanup
        return () => {
            window.removeEventListener('resize', handleResize);
            container.removeEventListener('mousedown', handleMouseDown);
            container.removeEventListener('wheel', handleWheel);
            window.removeEventListener('mousemove', handleMouseMove);
            window.removeEventListener('mouseup', handleMouseUp);

            if (animationFrameRef.current) {
                cancelAnimationFrame(animationFrameRef.current);
            }
            if (sceneRef.current) {
                sceneRef.current.renderer.dispose();
                if (container.contains(sceneRef.current.renderer.domElement)) {
                    container.removeChild(sceneRef.current.renderer.domElement);
                }
            }
            sceneRef.current = null;
        };
    }, [isConnected, status]); // Run once when connected and ready

    // Update camera aspect ratio when itemData changes (layout shifts from full width to 2/3 width)
    useEffect(() => {
        if (!sceneRef.current || !containerRef.current) return;

        // Use setTimeout to ensure DOM has updated after layout change
        const timer = setTimeout(() => {
            if (!containerRef.current || !sceneRef.current) return;
            const newWidth = containerRef.current.clientWidth;
            const newHeight = containerRef.current.clientHeight;
            sceneRef.current.camera.aspect = newWidth / newHeight;
            sceneRef.current.camera.updateProjectionMatrix();
            sceneRef.current.renderer.setSize(newWidth, newHeight);
            console.log('Camera aspect ratio updated:', newWidth, 'x', newHeight, '-> aspect:', newWidth / newHeight);
        }, 0);

        return () => clearTimeout(timer);
    }, [itemData]); // Re-run when itemData changes (triggers layout change)

    // Load model when itemData changes
    useEffect(() => {
        if (!sceneRef.current || !itemData?.model_obj) {
            if (!sceneRef.current) {
                console.log('Model load: sceneRef not ready yet');
            } else {
                console.warn('No model data provided by tool, showing cube');
                // Show cube if no model data
                const geometry = new THREE.BoxGeometry(2, 2, 2);
                const material = new THREE.MeshBasicMaterial({
                    color: 0x00ff00,
                    wireframe: true,
                });
                const cube = new THREE.Mesh(geometry, material);
                sceneRef.current.scene.add(cube);
                sceneRef.current.mesh = cube;
            }
            return;
        }

        const loader = new OBJLoader();

        console.log('=== PARSING DUCK MODEL FROM TOOL DATA ===');
        console.log('Duck OBJ data length:', itemData.model_obj.length);

        try {
            const object = loader.parse(itemData.model_obj);
            console.log('=== SUCCESS: Duck model parsed ===');
            console.log('Object:', object);

            // Apply wireframe material to all meshes
            object.traverse((child) => {
                if (child instanceof THREE.Mesh) {
                    child.material = new THREE.MeshBasicMaterial({
                        color: 0x00ff00,
                        wireframe: true,
                        wireframeLinewidth: 2,
                    });
                }
            });

            // Calculate bounding box BEFORE any transformations
            const box = new THREE.Box3().setFromObject(object);
            const center = box.getCenter(new THREE.Vector3());
            const size = box.getSize(new THREE.Vector3());

            console.log('Model bounds - min:', box.min, 'max:', box.max);
            console.log('Center before adjustment:', center);
            console.log('Size:', size);

            // Center the geometry by translating all vertices
            object.traverse((child) => {
                if (child instanceof THREE.Mesh && child.geometry) {
                    child.geometry.translate(-center.x, -center.y, -center.z);
                }
            });

            // Now the object is centered at origin, scale it to fit
            const maxDim = Math.max(size.x, size.y, size.z);
            const scale = 2 / maxDim;
            object.scale.setScalar(scale);

            console.log('Applied scale:', scale);
            console.log('Final object position:', object.position);

            // Remove old mesh if it exists
            if (sceneRef.current.mesh) {
                sceneRef.current.scene.remove(sceneRef.current.mesh);
            }

            sceneRef.current.scene.add(object);
            sceneRef.current.mesh = object;

            console.log('Model successfully centered and added to scene');
        } catch (error) {
            console.error('=== ERROR: Failed to parse duck model ===');
            console.error('Error object:', error);
            // Fallback to cube if model fails to parse
            console.log('Falling back to cube...');
            const geometry = new THREE.BoxGeometry(2, 2, 2);
            const material = new THREE.MeshBasicMaterial({
                color: 0x00ff00,
                wireframe: true,
            });
            const cube = new THREE.Mesh(geometry, material);

            // Remove old mesh if it exists
            if (sceneRef.current.mesh) {
                sceneRef.current.scene.remove(sceneRef.current.mesh);
            }

            sceneRef.current.scene.add(cube);
            sceneRef.current.mesh = cube;
            console.log('Cube fallback added');
        }
    }, [itemData]); // Re-run when itemData changes

    if (error) {
        return (
            <div style={{
                padding: '20px',
                fontFamily: '"Courier New", Courier, monospace',
                backgroundColor: '#0a0a0a',
                color: '#00ff00',
                height: '100vh'
            }}>
                <h2 style={{ color: '#ff0000', marginTop: 0 }}>ERROR</h2>
                <p>{error.message}</p>
            </div>
        );
    }

    if (!isConnected || status === 'connecting') {
        return (
            <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100vh',
                backgroundColor: '#0a0a0a',
                color: '#00ff00',
                fontFamily: '"Courier New", Courier, monospace',
                fontSize: '18px'
            }}>
                CONNECTING...
            </div>
        );
    }

    // Always render the 3D canvas when connected
    return (
        <div style={{
            position: 'relative',
            display: 'flex',
            width: '100vw',
            height: '100vh',
            overflow: 'hidden',
            backgroundColor: '#0a0a0a'
        }}>
            {/* Title indicator - replaces debug status */}
            {itemData && (
                <div style={{
                    position: 'absolute',
                    top: '10px',
                    left: '10px',
                    backgroundColor: '#00ff00',
                    color: '#0a0a0a',
                    padding: '5px 10px',
                    fontFamily: '"Courier New", Courier, monospace',
                    fontSize: '12px',
                    fontWeight: 'bold',
                    zIndex: 1000
                }}>
                    {itemData.name.toUpperCase()}
                </div>
            )}

            {/* Left Side - 3D Canvas Container (2/3) */}
            <div
                ref={containerRef}
                style={{
                    width: itemData ? '66.667%' : '100%',
                    height: '100%',
                    cursor: 'grab',
                    position: 'relative'
                }}
            />

            {/* Right Sidebar - Item Details (1/3) */}
            {itemData && (
                <div style={{
                    width: '33.333%',
                    height: '100%',
                    backgroundColor: '#0a0a0a',
                    padding: '10px',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'flex-start',
                    flexShrink: 0
                }}>
                    <div style={{
                        border: '2px solid #00ff00',
                        padding: '15px',
                        fontFamily: '"Courier New", Courier, monospace',
                        color: '#00ff00',
                        fontSize: '11px',
                        lineHeight: '1.5',
                        textTransform: 'uppercase',
                        letterSpacing: '0.5px'
                    }}>
                        <div style={{ fontSize: '14px', marginBottom: '12px', fontWeight: 'bold' }}>
                            {itemData.name}
                        </div>
                        <div style={{ borderTop: '1px solid #00ff00', paddingTop: '10px', marginBottom: '10px' }}>
                            <div style={{ marginBottom: '5px' }}>SKU: {itemData.sku}</div>
                            <div style={{ marginBottom: '5px' }}>TYPE: {itemData.type.replace('_', ' ')}</div>
                            <div style={{ marginBottom: '5px' }}>PRICE: €{itemData.unit_price.toFixed(2)}</div>
                            {itemData.uom && <div style={{ marginBottom: '5px' }}>UOM: {itemData.uom}</div>}
                            {itemData.reorder_qty && <div style={{ marginBottom: '5px' }}>REORDER QTY: {itemData.reorder_qty}</div>}
                        </div>
                        <div style={{
                            fontSize: '9px',
                            opacity: 0.7,
                            borderTop: '1px solid #00ff00',
                            paddingTop: '10px'
                        }}>
                            DRAG TO ROTATE • SCROLL TO ZOOM
                        </div>
                    </div>
                </div>
            )}

            {/* Retro scan lines effect (optional) */}
            <div style={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                background: 'repeating-linear-gradient(0deg, rgba(0, 255, 0, 0.03) 0px, rgba(0, 255, 0, 0.03) 1px, transparent 1px, transparent 2px)',
                pointerEvents: 'none'
            }} />
        </div>
    );
}
